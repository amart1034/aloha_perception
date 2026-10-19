# ALOHA Perception

Object detection, 3D localization, and camera-to-robot calibration for the ALOHA robotics system.

The long-term goal is to provide reliable object information to the motion-planning system for autonomous picking and other actions.

## Camera setup

- One overhead RealSense camera provides the primary view of the table.
- Two wrist cameras are planned for close-range observations.
- The current test uses only the overhead camera.

The overhead camera used during testing has serial number:

021222070323

Confirm the serial number before using these commands on another system.

## Current status

The pipeline has produced detections and opened an OpenCV viewer using:

- ROS 2 Humble.
- Intel RealSense D435i color and aligned depth.
- Standard pretrained YOLOv8s (yolov8s.pt).
- The target class truck.
- Camera-relative XYZ coordinates published as JSON inside a ROS text message.

The OpenCV viewer has exhibited freezing and repeated reopening. Instructions below include a temporary way to disable that viewer while inspecting detection output.

This detector does not command arm movement.

## First milestone

Use the overhead camera to:

1. Identify a target object, initially a toy fire truck.
2. Estimate its XYZ position using aligned depth.
3. Validate the position against physical measurements.

The standard pretrained model identifies the target as truck, rather than a separate fire-truck category. Recognition of the toy is not guaranteed in every view.

Camera-to-robot calibration is the next milestone. Camera-relative coordinates must not be treated as robot coordinates.

## Future work

- Validate coordinate accuracy.
- Calibrate the overhead camera relative to the robot.
- Add calibrated wrist-camera observations.
- Combine observations from multiple cameras.
- Track objects across camera views.
- Provide perception outputs to the motion-planning system.
- Improve visualization and handle missing or outdated observations.

## Prerequisites

Run these instructions on the computer physically connected to ALOHA and its overhead camera.

These instructions assume:

- ROS 2 Humble is installed at /opt/ros/humble.
- The existing ALOHA installation is in ~/interbotix_ws.
- ALOHA hardware permissions and configuration are already established.
- The RealSense ROS driver is installed.
- The detector code loads yolov8s.pt directly.
- You understand the lab's normal robot power-on and shutdown procedures.

Run each command block separately. Stop and inspect any error before continuing.

## 1. Download the repository

Open a terminal:

mkdir -p ~/interbotix_ws/src
cd ~/interbotix_ws/src

git clone https://github.com/amart1034/aloha_perception.git

If the repository already exists, update it instead:

cd ~/interbotix_ws/src/aloha_perception
git status
git pull --ff-only

If git status shows uncommitted changes, preserve and resolve them before pulling.

## 2. Load ROS and check dependencies

source /opt/ros/humble/setup.bash
source ~/interbotix_ws/install/setup.bash

Check the required Python imports:

python3 -c "import rclpy, message_filters, cv_bridge, cv2, numpy; from ultralytics import YOLO; print('Dependencies available')"

If an import fails, resolve the missing dependency in the Python environment used by ROS before continuing.

The detector version described here contains:

self.model = YOLO('yolov8s.pt')
self.target_classes = ['truck']

Ultralytics downloads the pretrained weights if they are not already available. The first download requires internet access and a writable download location.

This version does not require custom best.pt weights or a model_path argument.

## 3. Build the detector package

cd ~/interbotix_ws

colcon build --packages-select aloha_perception

source ~/interbotix_ws/install/setup.bash

Confirm the executable is registered:

ros2 pkg executables aloha_perception

Expected entry:

aloha_perception detector

Repeat the build and source commands after changing the Python code.

## 4. Identify the overhead camera

rs-enumerate-devices -s

The overhead camera used during testing was reported as:

RealSense D435I    021222070323

If your camera has a different serial, substitute it in the launch command.

Only one driver process should own the physical camera.

## 5. Terminal 1 — start ALOHA hardware

This step is optional for a camera-only test. Include it when testing alongside the robot hardware.

This starts real hardware and may enable motors. Follow the lab's power-on procedure, keep the workspace clear, and keep the emergency stop accessible.

Coordinate with anyone else using the robot. Do not start a second bringup if one is already running.

source /opt/ros/humble/setup.bash
source ~/interbotix_ws/install/setup.bash

ros2 launch aloha aloha_bringup.launch.py \
  robot:=aloha_stationary \
  use_cameras:=false

Leave this terminal running.

Use use_cameras:=false because the overhead camera will be started separately with explicit settings. This avoids starting drivers for the disconnected wrist cameras.

Keep MoveIt planners and teleoperation stopped during this perception test.

## 6. Terminal 2 — start the overhead camera

Open a new terminal:

source /opt/ros/humble/setup.bash
source ~/interbotix_ws/install/setup.bash

ros2 launch realsense2_camera rs_launch.py \
  camera_namespace:=cam_high \
  camera_name:=camera \
  serial_no:=_021222070323 \
  enable_color:=true \
  enable_depth:=true \
  align_depth.enable:=true \
  enable_infra1:=false \
  enable_infra2:=false \
  enable_gyro:=false \
  enable_accel:=false \
  pointcloud.enable:=false \
  rgb_camera.color_profile:=640,480,15 \
  depth_module.depth_profile:=640,480,15

Leave this terminal running.

This requests:

- Color images at 640 × 480 and 15 FPS.
- Depth images at 640 × 480 and 15 FPS.
- Depth aligned to the color image.
- Infrared image streams, IMU streams, and point-cloud processing disabled.

The expected camera node is:

/cam_high/camera

These arguments depend on the installed RealSense driver version. If an argument is rejected, inspect the error before continuing.

Do not start this driver alongside another process already using the camera.

## 7. Terminal 3 — verify camera parameters

Open another terminal:

source /opt/ros/humble/setup.bash
source ~/interbotix_ws/install/setup.bash

Check the unnecessary streams and processing:

ros2 param get /cam_high/camera enable_infra1
ros2 param get /cam_high/camera enable_infra2
ros2 param get /cam_high/camera enable_gyro
ros2 param get /cam_high/camera enable_accel
ros2 param get /cam_high/camera pointcloud.enable

If any return true, set them to false:

ros2 param set /cam_high/camera enable_infra1 false
ros2 param set /cam_high/camera enable_infra2 false
ros2 param set /cam_high/camera enable_gyro false
ros2 param set /cam_high/camera enable_accel false
ros2 param set /cam_high/camera pointcloud.enable false

These features are unnecessary for the current color-plus-depth detector.

Check that the required features are enabled:

ros2 param get /cam_high/camera enable_color
ros2 param get /cam_high/camera enable_depth
ros2 param get /cam_high/camera align_depth.enable

If any return false, set them to true:

ros2 param set /cam_high/camera enable_color true
ros2 param set /cam_high/camera enable_depth true
ros2 param set /cam_high/camera align_depth.enable true

Stop and inspect any failed parameter command.

Runtime changes may revert when the camera process restarts. The launch command above supplies the intended settings at startup.

## 8. Verify that camera frames are arriving

In Terminal 3:

ros2 node list
ros2 topic list

Confirm these topics exist:

/cam_high/camera/color/image_raw
/cam_high/camera/aligned_depth_to_color/image_raw
/cam_high/camera/color/camera_info

Check color-image delivery:

ros2 topic hz /cam_high/camera/color/image_raw

Wait for frequency readings, then press Ctrl+C.

Check aligned-depth delivery:

ros2 topic hz /cam_high/camera/aligned_depth_to_color/image_raw

Wait for frequency readings, then press Ctrl+C.

A topic appearing in ros2 topic list does not prove frames are arriving. Do not proceed until both streams produce readings.

## 9. Terminal 4 — start detection

Open another terminal:

source /opt/ros/humble/setup.bash
source ~/interbotix_ws/install/setup.bash

### Run without the OpenCV viewer

The viewer has exhibited freezing and repeated reopening. To inspect detection independently of that window, run:

DISPLAY= ros2 run aloha_perception detector --ros-args \
  -p rgb_topic:=/cam_high/camera/color/image_raw \
  -p depth_topic:=/cam_high/camera/aligned_depth_to_color/image_raw \
  -p info_topic:=/cam_high/camera/color/camera_info

DISPLAY= applies only to this command. The detector's existing display check should disable its OpenCV window.

This is a temporary workaround to evaluate, not a confirmed fix for the underlying viewer problem.

The startup log should report:

Loaded pretrained YOLOv8s ...
RealSense detection node ready

Leave the detector running and place the toy truck within the camera's view.

### Optional: run with the current OpenCV viewer

To try the existing viewer, stop the detector and rerun without DISPLAY=:

ros2 run aloha_perception detector --ros-args \
  -p rgb_topic:=/cam_high/camera/color/image_raw \
  -p depth_topic:=/cam_high/camera/aligned_depth_to_color/image_raw \
  -p info_topic:=/cam_high/camera/color/camera_info

A working graphical desktop session is required.

The viewer has exhibited freezing and repeated reopening. Stop the detector with Ctrl+C if that occurs.

## 10. Terminal 5 — inspect detection output

source /opt/ros/humble/setup.bash
source ~/interbotix_ws/install/setup.bash

ros2 topic echo /aloha/perception/detections

The output topic uses slashes:

/aloha/perception/detections

It is not:

/aloha_perception/detections

Successful detections contain:

| Field | Meaning |
|---|---|
| label | Predicted object category |
| confidence | Detection confidence |
| cx_3d | Camera-relative X in meters; positive right |
| cy_3d | Camera-relative Y in meters; positive down |
| cz_3d | Camera-relative depth in meters; positive forward |
| frame_id | Coordinate frame |
| stamp | Image capture timestamp |
| source | Detection source |

An illustrative result is:

[
  {
    "label": "truck",
    "confidence": 0.85,
    "cx_3d": 0.05,
    "cy_3d": -0.03,
    "cz_3d": 0.80,
    "frame_id": "camera_color_optical_frame",
    "stamp": 123.0,
    "source": "realsense"
  }
]

These values are examples, not measured results. The actual frame name comes from the camera message.

### Interpret the output

- A populated list means an accepted detection produced usable XYZ.
- [] means the processed frame produced no accepted object with usable depth.
- No messages may indicate missing camera inputs, synchronization problems, or processing errors. Inspect both the camera and detector terminals.

To measure output frequency, stop echo with Ctrl+C and run:

ros2 topic hz /aloha/perception/detections

Frequency readings confirm message delivery, not detection accuracy.

## 11. Optional — view the raw camera image

In another terminal:

source /opt/ros/humble/setup.bash
source ~/interbotix_ws/install/setup.bash

ros2 run rqt_image_view rqt_image_view

Select:

/cam_high/camera/color/image_raw

This displays the raw color image without detection overlays.

To inspect aligned depth, select:

/cam_high/camera/aligned_depth_to_color/image_raw

The current detector does not publish an annotated image topic to rqt.

## 12. Stop the system

1. Stop the detector with Ctrl+C.
2. Stop topic-monitoring commands with Ctrl+C and close rqt.
3. Stop the separate camera process with Ctrl+C.
4. Coordinate with anyone using ALOHA before stopping robot bringup.
5. Follow the lab's normal hardware power-down procedure.

Stopping ROS processes does not guarantee motor power is off.

## Coordinate interpretation and calibration

The published XYZ values are relative to the camera's optical frame:

- X increases to the right.
- Y increases downward.
- Z increases forward from the camera.

They estimate a visible surface point near the detection center, not necessarily the object's geometric center or a valid grasp point.

No manually published world transform is required for this test.

An earlier example placed the camera at (0, 0, 1) with zero rotation relative to world. That was a placeholder, not measured calibration, and should not be used to generate robot motion targets.

Camera-to-robot calibration must be measured and validated before the motion planner uses these positions.

## Troubleshooting

### Camera topic exists, but no frames arrive

A registered publisher can exist without delivering frames.

Check the camera terminal for messages such as:

Frames didn't arrive within 5 seconds
Frames Timeout

Then:

1. Confirm the physical camera's serial matches the launch command.
2. Confirm only one driver owns the camera.
3. Confirm unnecessary infrared, IMU, and point-cloud features are disabled.
4. Inspect the USB connection:

   lsusb -t

During troubleshooting, the camera was observed at 480M, indicating USB 2 speed. A USB 3-capable data cable and port are preferable. USB connectivity remains a possible contributor to timeouts, not a confirmed diagnosis.

### Camera starts under /camera/camera

Check the actual node and topic names:

ros2 node list
ros2 topic list

The launch command in this README requests /cam_high/camera.

If an existing camera instead runs under /camera/camera, use that node name for parameter checks and start detection with:

DISPLAY= ros2 run aloha_perception detector --ros-args \
  -p rgb_topic:=/camera/camera/color/image_raw \
  -p depth_topic:=/camera/camera/aligned_depth_to_color/image_raw \
  -p info_topic:=/camera/camera/color/camera_info

Confirm aligned depth is enabled and publishing before starting detection.

### Detector reports missing target_classes

Ensure this assignment exists inside __init__:

self.target_classes = ['truck']

Save, rebuild, load the workspace, and restart the detector.

### Detector publishes only empty lists

Possible causes include:

- The model does not recognize the toy.
- The target-class spelling does not match the model.
- Detection confidence is below the code's threshold.
- Depth near the detection center is missing or rejected.

Standard pretrained YOLO uses truck. The lab's custom model previously used fire-truck; these labels are not interchangeable.

### Detector loads an unexpected model or old code

After editing:

cd ~/interbotix_ws
colcon build --packages-select aloha_perception
source ~/interbotix_ws/install/setup.bash

Restart the detector process. Confirm the startup log names the expected model.

This README describes YOLOv8s (yolov8s.pt), matching the latest reported live test. Changing to YOLOv8m requires updating the model selection in the code and rebuilding.

### OpenCV viewer freezes or repeatedly reopens

Stop the detector and use the DISPLAY= startup command to disable its window.

Inspect detection messages and use rqt for the raw camera feed.

If detection messages also pause, investigate camera delivery and processing rather than assuming the issue is limited to visualization.

### Wrist-camera serial-number errors

This procedure connects only the overhead camera.

Starting full ALOHA bringup with use_cameras:=true may launch wrist-camera drivers that repeatedly search for disconnected devices.

Use the documented arrangement:

ALOHA bringup: use_cameras:=false
Overhead camera: separate RealSense launch

## Known limitations

- Coordinate accuracy has not yet been measured.
- Camera-to-robot calibration is not completed.
- The current test uses one camera.
- Multi-camera tracking and autonomous picking are future work.
- The OpenCV viewer issue remains unresolved.
- Object location alone does not specify grasp orientation or approach.
- Downstream robot control will need a policy for invalid, missing, and outdated observations.

## References

- Original ALOHA perception repository
- Lab ALOHA perception repository
- Kinova reference implementation
- ALOHA MoveIt reference