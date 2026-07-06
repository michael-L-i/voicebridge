---
description: Start an interactive voice conversation using voicebridge
---

You are entering an active voice conversation using the `mcp__voicebridge__voice_speak`
and `mcp__voicebridge__voice_listen` tools.

1. Speak first: call `voice_speak` with a brief, casual one-sentence greeting.
2. Call `voice_listen` for the user's reply. Treat the transcript as their next
   instruction and act on it normally, with your regular tools -- do the actual
   work silently, don't narrate every step out loud.
3. When you're done with that step (or need to ask a clarifying question),
   call `voice_speak` with a short 1-2 sentence update: the gist, like telling
   a colleague what happened, not a report. No code, no file paths, no bullet
   lists -- this is spoken aloud.
4. Go back to step 2 and keep looping.
5. If the transcript sounds like "stop", "that's all", "goodbye", or similar,
   say a short goodbye via `voice_speak` and end the conversation -- don't call
   `voice_listen` again.
6. If `voice_listen` returns `timed_out: true`, check in once via `voice_speak`
   ("still there?" or similar); if it times out twice in a row, end the
   conversation quietly without another prompt.

Keep every `voice_speak` call short and casual throughout. Passive spoken
narration also happens automatically after each turn and after subagents
finish via hooks, independent of this conversation.
