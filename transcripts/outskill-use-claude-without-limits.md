# Use Claude Without Limits (FREE 7.4 BILLION Tokens)

**Channel:** Outskill · **URL:** https://youtu.be/wVoWwo4P3BM
**Source:** Auto-generated YouTube transcript, provided by the user. Obvious speech-to-text errors are fixed (e.g. "Clawed" → Claude, "SAS" → SaaS, "envidia" → NVIDIA, "x-appi-key" → x-api-key). The wording is otherwise unchanged; section headings were added.

---

## 1. Hook

Here's a weird thing about AI right now. There are three or four models at the top. Claude, GPT, Gemini, all genuinely great. But the app a lot of people have built their workflow around is Claude. The projects, the artifacts, the thing that can actually touch files on your computer. Once you're in it, you don't want to leave.

But Anthropic put a meter on it. And that meter is the whole problem. Free plan, you hit it fast. $20 plan, you hit it in an afternoon of real work. $200 plan, a few days of heavy work, and you still hit it. Paying more doesn't remove the meter, it just moves it.

But what if I told you there's a way to get the same Claude app for free? Around 7.4 billion tokens a month. That's enough to build a full SaaS product, redesign your entire website, clean up years of messy files, and still have tokens left over at the end of the month. This 3D finance dashboard, built on it. This 3D website, $0. A messy laptop with over a thousand files, sorted in minutes, free.

And today I'll show you exactly how to set it up. Every key, every setting, every prompt, and the mistakes nobody warns you about, plus how to fix them. Stay till the end. I'll put a free alternative head-to-head with real Claude Opus 5.5. Same generic prompt, and you judge the result.

One small request before we start. Subscribe, because we're doing the work so your AI workflow becomes 100x more efficient. And all you have to do is build. Okay, let's dive in.

## 2. Sponsor: Outskill AI Mastermind

But before that, one thing worth mentioning, because it's the fastest way to actually get good at this stuff. That's what this weekend's free AI mastermind is built for. This Saturday and Sunday, Outskill is running a 2-day AI mastermind, live from 10:00 a.m. to 7:00 p.m. Eastern on both days. Over 10 million people have gone through this training. It's rated 4.9 out of five on Trustpilot and it normally costs $395. For the first thousand people from this video, it's free.

This isn't a lecture series. It's hands-on training from practitioners at Microsoft and NVIDIA covering more than 10 AI tools, AI inside Excel, Sheets, and Presentations, building your own AI agents, and automating your workflows. You also get a learning dashboard where you build alongside other people. Show up for both days and you also walk away with bonuses worth over $5,000, including a prompt bible, a road map to monetize AI, and a personalized AI toolkit builder. Seats are capped at 1,000, so grab yours through the first link in the description.

## 3. What this video covers

In my last video, I showed you three ways to stop paying for Claude Code. This one is different. Not Claude Code, the coding tool: the full Claude app, the one you already chat in, the one with projects, artifacts, Cowork. And instead of real Claude on a small free budget, we're running it on way bigger free fuel, up to around 7.4 billion tokens a month, from mostly open-source models that are good enough for everyday work. Different trade-off, different use case. Last time, real Claude, but small limits. This time, way more usage, but not Claude's brain. Both worth knowing.

By the end of this video, the Claude app on your computer will be running on free fuel. You'll clean up a messy laptop with it. You'll build a 3D finance dashboard on the same free engines. And you'll have a ladder of three different free setups so you can pick the one that fits your life. And one more thing, I'll put the easiest free alternative to Claude Code head-to-head with the real Claude on my paid plan. Same prompt, both results on screen. You decide which one wins. Let's go.

## 4. Step 1: Install Free LLM API

Step one, the one free app I mentioned. It's called Free LLM API and it's sitting on GitHub. Think of it as an app store for free tools, with over 50,000 stars. That's basically 50,000 developers saying, "I like this." Links in the description, so don't type anything, just click.

And look at the line right at the top of the page. 7.4 billion tokens a month, 34 free providers, 635 free model endpoints, all in one place. Quick note on tokens. It's just how AI usage is measured. One token is about 3/4 of a word. So 7.4 billion is more words than you could read in a lifetime.

Scroll down to Releases, that's the download section, and click the latest one. Windows: the file ending in setup.exe. Mac: the DMG, and if your Mac has an M chip, pick ARM64. Linux: the AppImage. And skip the zip files. That's the most common mistake here. On Windows, the zip files won't install at all.

Open it. Windows will say it protected your PC. Normal. That happens with a lot of new apps. Click More info, then Run anyway. A few seconds and it's installed. No account, no password, nothing to log into.

Quick tour, because you'll be living in these tabs. **Models**: every free AI you unlock. **Playground**: a chat box to test any of them. **Keys**: where we'll add our free keys in a minute. And **Agents**. Look at this list: Claude Code, Codex, Cursor, OpenCode, 20 AI tools this one app can plug into. Today, we're plugging it into the Claude app. But first, it needs fuel. And the fuel is free. You just need to know where to get it.

## 5. Step 2: Collect five free API keys

Fuel means API keys. And an API key is just a password that lets this app use a company's AI for you. Think of each one as a free fuel card. In the next 3 minutes, we'll collect five of them. By the end, you'll have hundreds of millions of free tokens in your tank. And the loop is the same every time: Add key, pick the company, grab the key from their site, copy, paste, save. Do it once, and the rest is muscle memory. Every link I mention is in the description, so don't type anything, just click.

**1. Google AI Studio.** Head to aistudio.google.com. Sign in with your Google account. Click Get API key. Then create a new key. Give it any name. Copy it. Back in Free LLM API, paste, Add key. It asks which models this key should serve. Hit Select all. Save. 15 Gemini and Gemma models. Free.

**2. NVIDIA.** This one's the big one. NVIDIA hosts some of the strongest open models in the world and lets you use them for free. Go to build.nvidia.com. Sign in. Click Generate API key. Name it. Set expiry to 12 months. Copy. Paste. Select all. Save. 16 more models. Two down, three to go.

**3. Z.AI**, the company behind the GLM models. Go to Z.AI. Sign in with Google. Open the API keys page. Click Add API key. Copy it. Paste. Save. Done in 30 seconds.

**4. Cloudflare.** Heads up, this one asks for two things instead of one. Don't worry, it's still quick. Go to dash.cloudflare.com and sign in. In the dashboard, open Workers AI, then REST API, and create a Workers AI API token. Don't worry about the names. Just follow my clicks. Copy it. The second thing is your account ID. It's that long code sitting right in the browser's address bar. Paste both. Add key. 26 more models unlocked.

**5. OpenRouter**, our safety net. Go to openrouter.ai, sign in, open the Keys page, create a new key, name it, set it to expire in 7 days, which means by the time you're watching this, my key is already dead. And here's a smart trick. Set the credit limit to $0. Now this key can only ever touch free models. Even if you wanted to spend money, you couldn't. Copy the key right away. OpenRouter shows it only once, and missing that is a really common mistake. Paste, Add key, done. And notice something: no credit card anywhere. No card means no bill.

**Bonuses (no key needed):** Parallel, which lets your AI search the web, and Kilo Gateway. Just click Enable on both.

Seven providers, all green, all healthy. Now look at the Models tab: around 788 million free tokens a month from just these keys. That's more words than you could type in your whole life. Add all 34 providers and you're up near 7.4 billion. But honestly, you don't need all of them. You need the best ones. And if you want to go wider later, there's a community list called **awesome-free-llm-apis** (links in the description) with dozens more free providers.

One more thing before we move on. Free LLM API isn't just chat. There's an **Image** tab for free AI image generation, and a **Fusion** tab where several AIs answer the same question and a judge picks the best answer. Both free. Worth a look later. Today we stay with chat.

## 6. Step 3: Add the strongest free models (custom endpoint)

But here's the catch nobody tells you. Most of these free engines are small. Good for everyday stuff, but not the heavy lifting. So next, let's go find the big ones, the strongest free engines we can get our hands on.

Remember the car from the last video? The Claude app is the body, the steering, the dashboard, everything you touch. The AI model is the engine. Right now, the engines we've put in are small. Good for a city drive, not built for the highway. So let's fit the strongest free engines we can find.

Back to Keys, click Add key, but this time choose **Custom endpoint**. All that means is, instead of letting the app pick which NVIDIA models to give you, we're going straight into NVIDIA's full catalog and picking the big ones ourselves. Type chat base URL: NVIDIA's full address. It's in the description, copy it from there. Use the same NVIDIA key you already generated. Click **Fetch models** and NVIDIA's whole catalog opens up.

I'm picking the heavy hitters first. **DeepSeek V4.1 Flash.** And here's why this one matters. There's an independent scoreboard called Artificial Analysis. They test every AI model that comes out and give it a score. DeepSeek V4.1 Flash scores 33. Claude's top model, Opus 5.5, on its lightest setting, scores 35. Two points. That's the entire gap between the thing people pay $200 a month for and the thing you just unlocked for zero.

And second, **GLM 5.3 Flash** from Z.AI. Another heavyweight. Add it. Both show up right here under Custom. All healthy. And you can add more the exact same way. Here's **MiniMax M3.1 Flash**. Fetch models. Tick, Add. That's it.

Now head to the Models tab. The **routing strategy** up top decides which AI answers when you send a message: Fastest, Smartest, Most reliable, or Manual if you want to pick the order yourself. I'll go with **Smartest**.

## 7. Step 4: Map models to Claude's Opus / Sonnet / Haiku slots

Now, here's where it all clicks. Head back to Keys and open the **Anthropic** tab inside it. The Claude app has three seats for AI models, named after Claude's own models: Opus, Sonnet, and Haiku. Opus is the top seat. Sonnet is the everyday workhorse. Haiku is the quick one. We get to decide what sits in each seat.

- **Opus** (top seat) → DeepSeek V4.1 Flash
- **Sonnet** (everyday seat) → GLM 5.3 Flash
- **Haiku** (quick one) → a fast Gemini Flash

Save mapping. Quick test in the Playground: "Hi, how are you doing?" Answer back in about a second and a half. The engines are running. Now, let's drop them into the car.

## 8. Step 5: Connect the Claude desktop app

Back on the Keys page, up top, you'll see your **unified API key**. One key that unlocks everything we just built. Copy it.

Now head to claude.com/download. Grab the Claude app for Windows. Install it. When it opens, don't sign in. Open the menu at the top left. Go to **Developer** and choose **Configure third-party inference**. That's a hidden setting that lets the Claude app run on a different engine. If you don't see Developer, turn on developer mode first. It's under Help, then Troubleshooting.

Now, five boxes. Miss one and nothing works. So pause here if you need to, and don't worry about what any of this means. Just mirror what's on screen. Everything is in the description, too.

1. **Type:** Gateway
2. **Credential kind:** Static API key
3. **Base URL:** `http://127.0.0.1:31415` (that's your own computer)
4. **API key:** paste the unified key you just copied
5. **Scheme:** `x-api-key`

Apply changes. Claude restarts, and look at the top of the window: "You're using Gateway." Open the model picker. Opus is now DeepSeek. Sonnet is GLM.

**Pro tip:** Picking one engine per seat is great when you have a favorite, but for everyday use, **Auto** is safer. So back in the Anthropic tab inside Free LLM API, set every seat to Auto and save. Now, if one engine is busy or hits its limit, Free LLM API quietly hands your message to the next healthy one. No errors, no waiting. You don't even notice the switch.

New chat. "Hi there." And it answers. Same Claude app you've always used, free engine inside it doing the work.

But you know the rule from the last video. The Claude app shows Claude's names everywhere: Opus, Sonnet, Haiku. And a model's word isn't proof. So check the receipt. Back in Free LLM API, open **Analytics**: every message, which model actually answered, which provider. The Claude app shows Claude. The proof shows you what really ran.

## 9. Demo 1: Cleaning up a messy laptop with Cowork

Setup's done. And if you've made it this far, this is your reward. Two real jobs. One everyday job you've been putting off for months, and one fun build that shows what free AI can actually do.

My laptop is a disaster. Downloads folder from 2022. Screenshots everywhere. Half-finished installer files I forgot about. So let's hand it to **Cowork**, the mode inside the Claude app that can actually read the files on your computer.

I asked Claude to look through my Desktop, Downloads, Documents, Pictures, Videos, and Music: "Don't move anything yet. Just tell me how bad it is, and never touch system folders." Claude asks permission for my user folder. Allow. And notice the model picker still says Haiku, but under the hood, a free engine is doing all this work. It writes its own little script, surveys everything. Read-only. Nothing moved yet.

And here's the verdict. Downloads folder: 997 files, 28.7 GB. Claude calls it the worst one. Fair. It also found duplicate files scattered across folders, old installers from apps I don't even use anymore. And it proposes a clean folder structure on its own.

Now I say go ahead. Claude builds a plan and starts moving files one folder at a time. And the log on my desktop is already filling up: every file, where it came from, where it went, why it moved. So if I don't like any of it, I can undo the whole thing. And Downloads now has real folders: installers in one place, photos in another, study files, videos, everything where it belongs.

Final summary: my desktop went from 54 files down to 11. 90 duplicates moved to the review folder. Nothing deleted. Every move logged. That's the kind of job most of us put off for months. Done in a few minutes, for free.

## 10. Demo 2: Building a 3D finance dashboard

Sorting files is useful, but can free AI actually build something? Let's find out. A 3D expense tracker in dollars. And this time, right inside Free LLM API's own Playground, set to Auto.

My prompt: dark navy background, glowing dollar coins floating in 3D, glass panels, add your expenses, a 3D chart, and a budget bar. Full text in the description.

Claude thinks through the 3D scene, then writes the whole app as one single file. And there's a live preview right here in the Playground. Version one: clean, dark, functional. Add-expense form on the right. Nice.

But I want more. So I talk to it the way I'd talk to a designer: "Make it professional. A long one-page tracker with charts and an analysis section. Here's a reference. I like Notion's finance tracker template." And for the redesign, I switched to a stronger engine, GLM 5.3 Flash.

And now look at this. **Expense Flow Pro**: a sidebar, overview cards for spending, income, cash flow, and budget, an income-versus-expenses chart, a monthly budget tracker, and a glowing 3D background that moves. All from a chat box, and it cost $0.

## 11. Troubleshooting: the safety net

Quick honesty check before we move on. So far I haven't hit a single error on camera, but free tools can break. Rate limits kick in, a provider goes down, something stops responding. It happens.

So here's your safety net, same house rule from the last video. If you ever see an error, copy the whole message. Open **Antigravity**, Google's free AI app that can actually fix things on your computer. Open the folder you were working in as your workspace, and tell it which folder that is. Paste the error and say, "Fix this." Or paste the Free LLM API GitHub link and say, "Follow this guide and fix my setup." Antigravity reads it, figures out what's wrong, fixes it. You carry on. You're the driver. Antigravity is the mechanic.

## 12. The simpler alternative: OpenCode

So that's Free LLM API: billions of free tokens running inside the real Claude app. But let's be honest, it takes setup. Keys to collect, engines to map. And free providers hit daily limits, slow down during busy hours, sometimes make you babysit them. So what if you want something simpler?

Here's the best part I promised you at the start. It's called **OpenCode**. You tell it what to build, it builds it, just like Claude Code, but some of the best free models on the planet are already baked in. No keys, no setup, no card. It's not identical to Claude Code, but the output is shockingly close, for free.

Head to opencode.ai, click Download, choose Windows, install it. Windows warning again: More info, Run anyway. Make an empty folder on your desktop. I'll call mine Brew Lab, and open it in OpenCode. Look at this list: DeepSeek, GLM, MiniMax, all free, all built in. I'm picking **DeepSeek V4.1 Flash (free)**, one of the strongest free models out there right now. And this version on OpenCode doesn't store your data or train on it.

## 13. Head-to-head: OpenCode (free) vs Claude Opus 5.5 ($200 plan)

And this time, I'm giving it almost nothing. Three lines:

> Build a stunning 3D website for a coffee shop called Brew Lab. Make it look like an award-winning website. Use Three.js and keep everything in one index.html file.

Three.js is just the tool websites use for 3D graphics. The design is completely up to the AI. It plans, it writes the file, and there's our website.

Now the exact same three lines, same prompt. This time I'm giving it to real Claude Opus 5.5, running on my paid plan.

And now both of them side by side. Left: Claude Opus 5.5, running on my $200-a-month plan. Right: DeepSeek V4.1 Flash, running completely free. Look at the hero sections, the typography, the 3D coffee animation on both sides, the scroll feel, the product cards, the menu. One of these costs $200 a month to make. The other one costs zero. I'll let you decide which one wins.

## 14. Your three options

So here's where you can go from here. Three options. Pick the one that fits your life.

1. **Free LLM API + the Claude app** (what we built today). The full Claude experience you already know, running on free engines that switch on their own. The biggest free setup out there and the most powerful, but it takes an afternoon to wire up.
2. **OpenCode.** Simpler, closest to Claude Code, with the best free models built in. No keys, no setup, nothing to configure. And if you ever want stronger engines, OpenCode Go is $10 a month.
3. **Real Claude models for free** (previous video). If you want the real Claude models, not open-source ones, go watch my last video. I showed three ways to run Claude Code for free using actual Claude Opus and Sonnet, plus around 1.6 billion more free tokens a month. Links up here.

## 15. Recap & outro

So let's add it up. Everyone told you Claude costs $20 a month, or 100, or 200. Today you put around 7.4 billion free tokens a month inside the real Claude app. It cleaned up a messy laptop. It built a 3D finance dashboard. And on top of that, you've got OpenCode, the simplest free alternative to Claude Code, with some of the best models on the planet. $0. No subscription, no credit card, no terminal.

Every prompt from this video, every link, every setting, it's all inside my free resource library. Links in the description. Join, grab everything, run your own build tonight.

And if you want to go way deeper than one video can take you, that's what this weekend's free AI mastermind is for. This Saturday and Sunday, Outskill is running a 2-day AI mastermind, live from 10:00 a.m. to 7:00 p.m. Eastern on both days. Over 10 million people have gone through this training. It's rated 4.9 out of five on Trustpilot. Normally costs $395. For the first thousand people from this video, it's free. Hands-on training from practitioners at Microsoft and NVIDIA. Over 10 AI tools, AI inside Excel, Sheets, presentations, building your own AI agents, automating your workflows, plus a learning dashboard where you build alongside other people. Show up for both days and you walk away with bonuses worth over $5,000: a prompt bible, a road map to monetize AI, a personalized AI toolkit builder. Seats capped at 1,000. First link in the description.

And drop a comment: what workflow do you want me to break down next? Our team actually reads them, and we pick the next video based on what you ask for. Subscribe. Free AI tools come and go, and when one of these breaks or a better one shows up, I'll make the next video. And if you want three more ways to run Claude Code for free, watch the video on screen. Catch you in the next one.

---

## Quick-reference: setup checklist

| Step | Action |
|---|---|
| 1 | Install **Free LLM API** from GitHub Releases (setup.exe / DMG-ARM64 / AppImage, not the zip) |
| 2 | Add keys: Google AI Studio, NVIDIA (build.nvidia.com), Z.AI, Cloudflare Workers AI (token + account ID), OpenRouter (credit limit $0) |
| 3 | Enable Parallel + Kilo Gateway (no key) |
| 4 | Custom endpoint → NVIDIA base URL → Fetch models → add DeepSeek V4.1 Flash, GLM 5.3 Flash, MiniMax M3.1 Flash |
| 5 | Models tab → routing strategy: Smartest |
| 6 | Keys → Anthropic tab → map Opus/Sonnet/Haiku (or set all to Auto) |
| 7 | Copy the unified API key |
| 8 | Claude desktop → Developer → Configure third-party inference: Gateway · Static API key · `http://127.0.0.1:31415` · unified key · `x-api-key` |
| 9 | Verify which model actually answered in Free LLM API → Analytics |
