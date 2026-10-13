# ALOHA Perception

Object detection, 3D localization, and camera-to-robot calibration
for the ALOHA robotics system.

## Camera setup

- One overhead camera for the primary view of the table.
- Two wrist cameras for close-range observations.

## First milestone

Use the overhead camera to:
1. Identify an object.
2. Estimate its XYZ position using aligned depth.
3. Validate the position against physical measurements.
4. Transform the position into a calibrated robot coordinate frame.

## Future work

- Combine observations from all three cameras.
- Track objects across camera views.
- Provide perception outputs to the motion-planning system.

## References

- https://github.com/VigneshT24/aloha_yolo_perception
- https://github.com/Shashy2305/KinovaARM
