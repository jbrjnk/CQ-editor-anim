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