# Patchwork
Distributed rendering with deliverable-diffing for DaVinci Resolve!

## Pitch
Imagine Git diffing for DaVinci Resolve renders...
Patchwork diffs your old renders with your current timeline and only re-renders changes you've made. 
Even with inter-frame compression codecs like h.264. 

### Why?
Complex renders can take a long time and a small change shouldn't warrant a complete re-render. You also have to quality check each render for corruption, artifacting, green or black frames, offline-media, etc. sax This way you only have to check what you've re-rendered. It also allows chunking jobs and using multiple DaVinci Resolve remote-rendering machines to work on a single render. Again, even with inter-frame compression codecs, like h.264. Theoretically, renders will only take as long as computers you have free (or rather, Resolve licenses you own!). Sometimes deadline dramas warrant dropping all projects and focussing resources on a single deliverable.

## Proposal

There's a long road ahead for this project. Doing things in stages will be the best way to keep sane and not get overwhelmed.
We'll probably start by creating a custom workflow integration for rendering that hooks into Resolve's Python API. We can get a .fcpxml file exported of the entire timeline, diff it with the one from the last export and use that to inform which sections we re-render. Final Cut XML is a popular editorial format that most NLEs support. It has strong support in OpenTimelineIO, which we can use for the heavy lifting. It doesn't support fancy speed effects, colour-grade data, fusion compositions or fairlight effects, but no non-Resolve-native format does. Maybe sometime down the line we'll look into diffing .drt (DaVinci Resolve timelines), but .fcpxml is enough of a handful without support for the extra data and the non-existent specs or docs for .drt. It is forbidden territory. 

We could even support diffing initial renders delivered through Resolve natively by using pre-render script hooks built into export presets to export .fcpxml files of the timeline on render. Of course this only works for the initial state but at least it means users won't have to use the workflow integration for every render they want to support.

There's a lot of research and territory to cover.
Here are some of my initial notes:

---

#### How do we actually Diff?
Well we need to consider scope. Git diffs line by line. What's that look like for video? We need our scope to be something realistic. How small are we going to make our diffs? Do we support something as granular as keyframe changes? Do we have a minimum chunk render size? (well keyframe to keyframe will be the **absolute** minimum)

We need to be able to support changes to a few things:

###### Edits
If we look at the edit index panel, we can see how rolling/sliding/trimming edits affects the source-in and source-out values of a clip. If we can get the record-in and record-out values as well, we know exactly where that clip is on the timeline and where to splice our render. This only works for changes to edit timing though!

###### Speed
Clip speed is a hairy one. Every NLE has a different way of representing it in their project/timeline files. We have to consider how to support both keyframe-based retiming and global clip retiming.

###### Transformations
Changes to zoom, position, rotation, pitch, yaw, opacity. They're just the tip of the transformation iceberg. We also have stabilisation, cropping, dynamic zoom, composite mode, lens correction, retime/scaling settings to consider. Then there are Resolve effects, like standard titles, adjustment layers and what not **AND** OFX effects (that can even be third-party) that apply their own transformations. How do we support all of those?

###### Fusion
This is where things get really hairy. Fusion is a completely different program with a different history that has been slowly transplanted into Resolve. How does it store data? I clearly can't export a fusion composition in any timeline format that isn't a DRT. Even then, how does a DRT store that reference to the fusion composition? With an ID to a database asset? We'd end up having to query the database for that data anyway. Either we don't support fusion compositions and we throw a little tantrum if we detect them, or we go the whole hog and connect straight to postgres.

###### Colour
Ayah. Don't expect to be finding changes to colour in .fcpxml exports. It's DRT, database or go home.

###### Fairlight
Same thing as the colour page but for audio. Custom effects cannot be exported in a format other than a DaVinci Resolve timeline. We could get away with always rendering the audio again, but this will still add significant extra time to export, especially for long timelines.

###### Project
If we make any global changes to the project, i.e. in project settings, they will affect the whole timeline. That warrants an entire timeline re-render. It would be nice to be able to catch these changes and warn the user. We could do that ahead of time if we listen to the database, or we could do it with pre-queue diffing and hopefully be able to tell the user what they changed that warrants a full re-render.

###### Deliverable Settings
Not to be overlooked, but very close to having been! Deliverable settings must match between renders. That includes in and outs as well as format and codecs settings. Since in and outs need to match, either we disallow them and only support rendering entire timelines, or we need to be able to set and get render in and out programmatically.
