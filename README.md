# Patchwork
Accelerated encoding for DaVinci Resolve.

Well the above is a bit of deception... It's like Rich Harris of Svelte says:
> "The fastest code is no code".

Instead of fully re-rendering a deliverable, patch it.

### What?
I was inspired by Git. When you pull from your repo, it doesn't download everything from scratch. Of course it doesn't. How inconvenient. Why then do NLE's still re-render videos in their entirety for minor changes instead of just re-exporting the changed segments and splicing them into the original?

Re-rendering an entire deliverable is almost always inconvenient. Complex renders can take a long time and a small change shouldn't warrant a complete re-render. Since the entire file is re-written, it also becomes important to QC the deliverable again in it's entirety: corruption, artifacting, green or black frames, offline-media, etc, are all risk-factors, despite an otherwise minor, narrow change. With lossless patching, you only have to check what you've re-rendered. 

Okay, so that makes subsequent renders faster. But with multiple computers, it also makes the initial render faster.
Splitting the initial render a into multiple segments allows for the job to be distributed to multiple computers with Resolve's built in remote-render functionality. Traditionally remote-render is reserved for a queue of individual deliverables, not parallel computing on a single job. By splitting and joining at nearest GOP I-frames, inter-frame compression codecs can also be supported.

### How?
1. Calculate changes/segments
2. Queue using DaVinci Resolve's Python API
3. Concatenate losslessly with Ffmpeg

## Roadmap
- [x] Initial logic and GUI
- [ ] Support patching all-intra codecs
- [ ] Support patching inter-frame codecs
- [ ] Support automatic diffing (no manually marked changes)
