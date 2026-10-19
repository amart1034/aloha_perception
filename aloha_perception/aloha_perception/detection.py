#!/usr/bin/env python3
"""
RealSense D435I object detection node.
Uses YOLOv8m + HSV color fallback.
Publishes to /detections_side: camera-frame coords (cx_3d/cy_3d/cz_3d) plus
the image frame_id. scene_graph_node converts them to base_link through TF
(base_link -> global_camera_color_optical_frame, the easy_handeye2 result).
"""
import os
import rclpy, threading, json
import message_filters
from rclpy.qos import qos_profile_sensor_data
from rclpy.node import Node
from sensor_msgs.msg import Image, CameraInfo
from std_msgs.msg import String
from cv_bridge import CvBridge
import cv2, numpy as np

try:
    from ultralytics import YOLO
    YOLO_AVAILABLE = True
except:
    YOLO_AVAILABLE = False

class RealSenseDetection(Node):
    def __init__(self):
        super().__init__('realsense_detection')

        self.bridge  = CvBridge()
        self.fx = self.fy = self.cx = self.cy = None
        self.depth   = None
        self._lock   = threading.Lock()
        # Debug preview window needs a real X11/Wayland display -- fine with
        # someone logged into the GUI session, fatal (Qt xcb plugin abort)
        # running headless over SSH, which is how this node runs on REAL-1.
        self._has_display = bool(os.environ.get('DISPLAY'))

        # Blocked (no detections published) if camera_watchdog flagged this
        # camera for recalibration after a drop/reconnect. See
        # camera_watchdog.py / multi_camera_calibrate.py.
        self._blocked = False
        self.create_subscription(
            String, '/camera_calibration_status', self._calibration_status_cb, 10)

<<<<<<< HEAD
        # YOLO
        self.model = None
        if YOLO_AVAILABLE:
            default_model_path = os.path.join(
                get_package_share_directory('thesis_robot'), 'models', 'yolov8m.pt')
            self.declare_parameter('model_path', default_model_path)
            model_path = self.get_parameter('model_path').value
            try:
                self.model = YOLO(model_path)
                self.get_logger().info(f'YOLOv8m loaded')
            except Exception as e:
                self.get_logger().warn(f'YOLO failed: {e} — using color detection only')
=======
        self.target_classes = ['fire-truck']

        # Receive color, depth aligned to color, and color-camera calibration info
        self.declare_parameter('rgb_topic', '/cam_high/camera/color/image_raw')
        self.declare_parameter('depth_topic', '/cam_high/camera/aligned_depth_to_color/image_raw')
        self.declare_parameter('info_topic', '/cam_high/camera/color/camera_info')
>>>>>>> 4e0c7c8621593d26f729da152ce703af3bb15998

        self.target_classes = [
            'bottle', 'cup', 'bowl', 'cell phone',
            'remote', 'book', 'scissors', 'vase', 'mouse'
        ]

        # Subscriptions — use aligned depth (perfect alignment with RGB)
        self.create_subscription(
            Image, '/global_camera/global_camera/color/image_raw', self._rgb_cb, 10)
        self.create_subscription(
            Image, '/global_camera/global_camera/aligned_depth_to_color/image_raw',
            self._depth_cb, 10)
        self.create_subscription(
            CameraInfo, '/global_camera/global_camera/color/camera_info', self._info_cb, 10)

        self.det_pub = self.create_publisher(String, '/detections_side', 10)
        self.get_logger().info('RealSense detection node ready')

    def _info_cb(self, msg):
        fx = msg.k[0]
        fy = msg.k[4]
        cx = msg.k[2]
        cy = msg.k[5]

        if not np.isfinite([fx, fy, cx, cy]).all() or fx <= 0 or fy <= 0:
            self.get_logger().warn(
                'Received invalid camera parameters'
            )
            return

        self.fx = fx
        self.fy = fy
        self.cx = cx
        self.cy = cy
        self.camera_info = msg
    def _images_cb(self, rgb_msg, depth_msg):
        if self.camera_info is None:
            return
        
        if (self.camera_info.header.frame_id != rgb_msg.header.frame_id) or (self.camera_info.width != rgb_msg.width) or (self.camera_info.height != rgb_msg.height):
            self.get_logger().warn('Color Camera does not match color image')
            return

        if depth_msg.encoding != '16UC1':
            self.get_logger().warn(
                f'Expected 16UC1 depth, received {depth_msg.encoding}'
            )
            return

        if (rgb_msg.width, rgb_msg.height) != (
            depth_msg.width, depth_msg.height
        ):
            self.get_logger().warn(
                'Color and aligned depth dimensions do not match'
            )
            return

        if (
            not rgb_msg.header.frame_id
            or rgb_msg.header.frame_id != depth_msg.header.frame_id
        ):
            self.get_logger().warn(
                'Color and aligned depth coordinate frames do not match'
            )
            return

        try:
            depth = self.bridge.imgmsg_to_cv2(depth_msg, '16UC1')
        except Exception as exc:
            self.get_logger().warn(f'Could not convert depth image: {exc}')
            return

        with self._lock:
            self.depth = depth

        self._rgb_cb(rgb_msg)

    def _get_depth(self, u, v):
        with self._lock:
            if self.depth is None:
                return 0.0
            h, w = self.depth.shape
            u = max(0, min(u, w-1))
            v = max(0, min(v, h-1))
            patch = self.depth[
                max(0,v-8):min(h,v+8),
                max(0,u-8):min(w,u+8)]
            valid = patch[patch > 0]
            if len(valid) == 0:
                return 0.0
            return float(np.median(valid)) / 1000.0

    def _backproject(self, u, v, depth_m):
        if depth_m < 0.1 or self.fx is None:
            return None
        cx3 = (u - self.cx) * depth_m / self.fx
        cy3 = (v - self.cy) * depth_m / self.fy
        cz3 = depth_m
        return cx3, cy3, cz3

    def _color_detect(self, bgr):
        """HSV color fallback detection."""
        hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
        detections = []
        color_ranges = {
            'red_obj':    [(0,120,70),(10,255,255),(170,120,70),(180,255,255)],
            'blue_obj':   [(100,100,70),(130,255,255),None,None],
            'green_obj':  [(40,100,70),(80,255,255),None,None],
            'yellow_obj': [(20,100,70),(35,255,255),None,None],
        }
        for name, (lo1,hi1,lo2,hi2) in color_ranges.items():
            m1 = cv2.inRange(hsv, np.array(lo1), np.array(hi1))
            if lo2:
                m2 = cv2.inRange(hsv, np.array(lo2), np.array(hi2))
                mask = cv2.bitwise_or(m1, m2)
            else:
                mask = m1
            k = np.ones((7,7), np.uint8)
            mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, k)
            mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, k)
            cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            if not cnts:
                continue
            c = max(cnts, key=cv2.contourArea)
            if cv2.contourArea(c) < 500:
                continue
            M = cv2.moments(c)
            if M['m00'] == 0:
                continue
            u = int(M['m10']/M['m00'])
            v = int(M['m01']/M['m00'])
            detections.append((name, 0.75, u, v))
        return detections

    def _rgb_cb(self, msg):
        if self.fx is None:
            return

        try:
            rgb = self.bridge.imgmsg_to_cv2(msg, 'rgb8')
            bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
        except Exception as e:
            return

        raw_detections = []

        # yolo detection
        if self.model is not None:
            try:
                results = self.model(bgr, verbose=False)
                for r in results:
                    for box in r.boxes:
                        cls_name = self.model.names[int(box.cls)]
                        if cls_name not in self.target_classes:
                            continue
                        conf = float(box.conf)
                        if conf < 0.30:
                            continue
                        x1,y1,x2,y2 = map(int, box.xyxy[0])
                        u = (x1+x2)//2
                        v = (y1+y2)//2
                        raw_detections.append((cls_name, conf, u, v))
            except Exception as e:
                self.get_logger().warn(f'YOLO error: {e}')


        if not raw_detections:
            self.det_pub.publish(String(data='[]'))
            return

        detections = []
        display = bgr.copy()

        for label, conf, u, v in raw_detections:
            depth_m = self._get_depth(u, v)
            if depth_m < 0.1:
                continue
            coords = self._backproject(u, v, depth_m)
            if coords is None:
                continue
            cx3, cy3, cz3 = coords

            detections.append({
                'label':      label,
                'confidence': round(conf, 3),
                'cx_3d':      round(cx3, 4),
                'cy_3d':      round(cy3, 4),
                'cz_3d':      round(cz3, 4),
                'frame_id':   msg.header.frame_id,
                'stamp':   msg.header.stamp.sec + msg.header.stamp.nanosec * 1e-9,
                'source':     'realsense',
            })

            cv2.circle(display, (u,v), 6, (0,255,0), -1)
            cv2.putText(display,
                f"{label} {conf:.0%} z={depth_m:.2f}m",
                (u+8, v), cv2.FONT_HERSHEY_SIMPLEX,
                0.5, (0,255,0), 2)

        self.det_pub.publish(String(data=json.dumps(detections)))

        if self._has_display:
            cv2.imshow('RealSense Detection', display)
            cv2.waitKey(1)

def main(args=None):
    rclpy.init(args=args)
    node = RealSenseDetection()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    if node._has_display:
        cv2.destroyAllWindows()

if __name__ == '__main__':
    main()
