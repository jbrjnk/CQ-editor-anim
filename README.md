# Fork of CadQuery editor supporting model animation

The goal of this fork is to add ability to animate 3D model. The principle of this function is to execute the script for each timepoint and capture the rendered model to a bitmap file (*.png). The resulting set of frames can be used to generate video (using another tool, ffmpeg for example)

## Description
The newly added widget `animation` allows to configure all necessary parameters

<img src="https://github.com/jbrjnk/CQ-editor-anim/blob/master/screenshots/anim_screenshot1.png" alt="Screenshot" width="70%" >

* `Width` - the horizontal size of captured frame (in pixels)
* `Height` - the vertcal size of captured frame (in pixels)
* `Frame index` - timepoint of frame shown as preview
* `Output folder` - location where captured frames will be stored


The displayed preview is rendered according to these parameters. Once the 'Capture frames' button is pressed, the program starts to iteratively execute the script  until the end of the animation is reached.

## How to create animated model
There are a few new functions available within the script which are necessary to be used to generate animated model.
### Animation related functions
* `animation_getFrameIndex() -> int` - Returns the zero-based index of currently rendered frame.
* `animation_isActive() -> bool` - Returns `True` if animation is running (i.e. script is executed because of pressing "Refresh preview" or "Capture frames" button on animation widget).

### View related function
* `view_setAt(x : float, y : float, z : float)` - Sets target of view
* `view_setUp(x : float, y : float, z : float)` - Sets up direction
* `view_setProj(x : float, y : float, z : float)` - Sets projection orientation
* `view_setScale(scale : float)` - Sets zoom level

These functions just call the corresponding function on V3D_View object, for more information see <a href="https://dev.opencascade.org/doc/refman/html/class_v3d___view.html"> documentation </a> 

## Sample of animated 3D model
```
import cadquery as cq
import math

camAngle = animation_getFrameIndex() # camera view direction angle
if camAngle == 3 * 360 - 1: # 3 * 360 - 1 is the zero based index of the last frame (3 * 360 is total number of frames)
    animation_complete() # end of animation


angle = camAngle * 3.8 # disk rotationAngle

if animation_isActive():
    view_setAt(0,0,0)
    view_setProj(math.sin(math.radians(camAngle)), -math.cos(math.radians(camAngle)), 1)
    view_setUp(0, 0, 1)
    view_setScale(6)

result = cq.Workplane("XZ").circle(50).extrude(6)\
            .workplane(origin = cq.Vector(50, 0, 0)).circle(5).extrude(8, both=True)\
            .rotateAboutCenter(cq.Vector(0,-1,0), angle)
```
Resulting animated GIF (truncated):

<img src="https://github.com/jbrjnk/CQ-editor-anim/blob/master/screenshots/sample-animation.gif" />

## Making videofile or animated GIF
The videofile or animated GIF can be generated using tools like ffmpeg. For example:

### Animated GIF
`ffmpeg.exe -framerate 18 -i "%06d.png" -vf "scale=256:-1"  output.gif`

This command makes animated GIF from all PNG files in working directory. The animation is 256 pixels width and the speed is 18 frames per second. (`%06d.png` is pattern matching names of PNG files)

### Videofile
`ffmpeg.exe  -framerate 25 -i "%06d.png" -vcodec mpeg4 -b:v 4M  output10.mp4`

## Issues
The current implementation has the following issues:
* It completely runs on main UI thread. Due to this fact, the window responds a little bit slow (UI events are handled during capturing frames, but with a small delay). I think it would be better create another instance of 3D viewer widget in background thread and make rendering independent on UI (I didn't investigate if it's possible)
* I didn't find the way how to get bitmap frame from 3D viewer widget that works completely in-memory. The `Data()` function (member of `Image_PixMap` class) returns just one number instead of the whole array (probably due to the same issue as described <a href="https://github.com/CadQuery/pywrap/issues/51">here</a>). For this reason, the frame is always stored to the file and then loaded back to be shown as preview.

These issues have impact on user experience only, they don't affect the output.