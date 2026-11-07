"""Model engines for Studio. Each engine lazily loads an open-source model.

Only one heavy model is kept in memory at a time, so a single consumer GPU
can switch between voice, image and video work.
"""
import gc
import math
import os
import struct
import wave
import zlib
from pathlib import Path

FAKE = os.getenv("STUDIO_FAKE") == "1"  # plumbing tests without downloading models

_cache = {"key": None, "model": None}


def device() -> str:
    import torch
    if torch.cuda.is_available():
        return "cuda"
    if torch.backends.mps.is_available():
        return "mps"
    return "cpu"


def _load(key, loader):
    """Return a cached model, unloading whatever else is resident first."""
    if _cache["key"] == key:
        return _cache["model"]
    _cache["key"], _cache["model"] = None, None
    gc.collect()
    try:
        import torch
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except ImportError:
        pass
    model = loader()
    _cache["key"], _cache["model"] = key, model
    return model


def _offload(pipe):
    """Fit big pipelines on smaller GPUs: offload to CPU when not on a 24GB+ card."""
    import torch
    dev = device()
    if dev == "cuda":
        vram = torch.cuda.get_device_properties(0).total_memory / 1e9
        if vram < 24:
            pipe.enable_model_cpu_offload()
        else:
            pipe.to("cuda")
    else:
        pipe.to(dev)
    return pipe


# ---------------------------------------------------------------- voice (TTS)
KOKORO_VOICES = {
    "af_heart": "US female - warm", "af_bella": "US female - bright",
    "am_michael": "US male - calm", "am_fenrir": "US male - deep",
    "bf_emma": "UK female", "bm_george": "UK male",
    "hf_alpha": "Hindi female", "hm_omega": "Hindi male",
}


def tts(text: str, voice: str, speed: float, out: Path) -> Path:
    """Fast stock-voice TTS with Kokoro (Apache-2.0, runs fine on CPU)."""
    if FAKE:
        return _fake_wav(out, len(text.split()) / 2.5)
    import numpy as np
    import soundfile as sf
    from kokoro import KPipeline

    lang = voice[0]  # a=US, b=UK, h=Hindi ...
    pipe = _load(f"kokoro-{lang}", lambda: KPipeline(lang_code=lang))
    chunks = [audio for _, _, audio in pipe(text, voice=voice, speed=speed)]
    sf.write(out, np.concatenate(chunks), 24000)
    return out


def clone(text: str, reference: Path, exaggeration: float, out: Path) -> Path:
    """Voice cloning from a ~10s reference clip with Chatterbox (MIT)."""
    if FAKE:
        return _fake_wav(out, len(text.split()) / 2.5)
    import torchaudio
    from chatterbox.tts import ChatterboxTTS

    model = _load("chatterbox", lambda: ChatterboxTTS.from_pretrained(device=device()))
    wav = model.generate(text, audio_prompt_path=str(reference),
                         exaggeration=exaggeration, cfg_weight=0.5)
    torchaudio.save(str(out), wav, model.sr)
    return out


# ------------------------------------------------------------------- image
def image(prompt: str, width: int, height: int, seed: int, out: Path) -> Path:
    """Text-to-image with FLUX.1-schnell (Apache-2.0, 4 steps)."""
    if FAKE:
        return _fake_png(out)
    import torch
    from diffusers import FluxPipeline

    pipe = _load("flux", lambda: _offload(FluxPipeline.from_pretrained(
        "black-forest-labs/FLUX.1-schnell", torch_dtype=torch.bfloat16)))
    gen = torch.Generator("cpu").manual_seed(seed)
    img = pipe(prompt, width=width, height=height, num_inference_steps=4,
               guidance_scale=0.0, generator=gen).images[0]
    img.save(out)
    return out


# ------------------------------------------------------------------- video
NEGATIVE = "worst quality, blurry, jittery, distorted, watermark, text, deformed hands"


def video(prompt: str, model: str, seconds: int, start_image: Path | None, out: Path) -> Path:
    """Text/image-to-video. 'ltx' = fast drafts, 'wan' = higher quality."""
    if FAKE:
        out.write_bytes(b"")
        return out
    import torch
    from diffusers.utils import export_to_video, load_image

    fps = 24
    if model == "wan":
        from diffusers import AutoencoderKLWan, WanPipeline
        repo = "Wan-AI/Wan2.2-TI2V-5B-Diffusers"

        def load():
            vae = AutoencoderKLWan.from_pretrained(repo, subfolder="vae", torch_dtype=torch.float32)
            return _offload(WanPipeline.from_pretrained(repo, vae=vae, torch_dtype=torch.bfloat16))

        pipe = _load("wan", load)
        frames = (seconds * fps // 4) * 4 + 1  # Wan wants 4k+1 frames
        result = pipe(prompt=prompt, negative_prompt=NEGATIVE, height=704, width=1280,
                      num_frames=frames, guidance_scale=5.0, num_inference_steps=40)
    else:
        from diffusers import LTXImageToVideoPipeline, LTXPipeline
        frames = (seconds * fps // 8) * 8 + 1  # LTX wants 8k+1 frames
        kwargs = dict(prompt=prompt, negative_prompt=NEGATIVE, width=768, height=512,
                      num_frames=frames, num_inference_steps=40)
        if start_image:
            pipe = _load("ltx-i2v", lambda: _offload(LTXImageToVideoPipeline.from_pretrained(
                "Lightricks/LTX-Video", torch_dtype=torch.bfloat16)))
            kwargs["image"] = load_image(str(start_image))
        else:
            pipe = _load("ltx", lambda: _offload(LTXPipeline.from_pretrained(
                "Lightricks/LTX-Video", torch_dtype=torch.bfloat16)))
        result = pipe(**kwargs)
    export_to_video(result.frames[0], str(out), fps=fps)
    return out


# --------------------------------------------------------- captions (STT)
def captions(media: Path, out: Path) -> Path:
    """Transcribe audio/video to an .srt with faster-whisper (MIT)."""
    if FAKE:
        out.write_text("1\n00:00:00,000 --> 00:00:01,000\nTest caption\n")
        return out
    from faster_whisper import WhisperModel

    gpu = device() == "cuda"
    model = _load("whisper", lambda: WhisperModel(
        "large-v3" if gpu else "small", device="cuda" if gpu else "cpu",
        compute_type="float16" if gpu else "int8"))
    segments, _ = model.transcribe(str(media), vad_filter=True)

    def ts(t):
        h, rem = divmod(t, 3600)
        m, s = divmod(rem, 60)
        return f"{int(h):02}:{int(m):02}:{int(s):02},{int((s % 1) * 1000):03}"

    lines = [f"{i}\n{ts(s.start)} --> {ts(s.end)}\n{s.text.strip()}\n"
             for i, s in enumerate(segments, 1)]
    out.write_text("\n".join(lines))
    return out


# ------------------------------------------------------------ fake outputs
def _fake_wav(out: Path, seconds: float = 1.0) -> Path:
    second = b"".join(struct.pack("<h", int(3000 * math.sin(i / 10))) for i in range(24000))
    with wave.open(str(out), "w") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(24000)
        w.writeframes(second * int(seconds) + second[: int(seconds % 1 * 24000) * 2])
    return out


def _fake_png(out: Path) -> Path:
    def chunk(t, d):
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d))
    raw = b"\x00\x80\x80\xff"
    out.write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
                    + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))
    return out


# ------------------------------------------------------- avatar (lip-sync)
def lipsync(face_video: Path, audio: Path, out: Path) -> Path:
    """Make your own footage say new lines, using LatentSync (Apache-2.0).

    One-time setup (NVIDIA GPU, ~8GB+ VRAM):
      git clone https://github.com/bytedance/LatentSync && cd LatentSync && bash setup_env.sh
      export LATENTSYNC_DIR=/path/to/LatentSync LATENTSYNC_PY=/path/to/its/python
    The face video should be 10-60s of you facing camera, mouth visible, little head turning.
    """
    import subprocess

    if FAKE:
        import shutil
        shutil.copy(face_video, out)
        return out
    repo = os.getenv("LATENTSYNC_DIR")
    if not repo:
        raise RuntimeError("Avatar scenes need LatentSync: set LATENTSYNC_DIR (see engines.lipsync)")
    # loop the face footage to cover the whole line before syncing
    looped = out.with_name(out.stem + "_src.mp4")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-stream_loop", "-1", "-i", str(face_video),
                    "-i", str(audio), "-map", "0:v", "-map", "1:a", "-shortest",
                    "-c:v", "libx264", "-preset", "veryfast", "-r", "25", str(looped)], check=True)
    subprocess.run([os.getenv("LATENTSYNC_PY", "python"), "-m", "scripts.inference",
                    "--unet_config_path", "configs/unet/stage2.yaml",
                    "--inference_ckpt_path", "checkpoints/latentsync_unet.pt",
                    "--inference_steps", "20", "--guidance_scale", "1.5",
                    "--video_path", str(looped.resolve()), "--audio_path", str(audio.resolve()),
                    "--video_out_path", str(out.resolve())], cwd=repo, check=True)
    return out
