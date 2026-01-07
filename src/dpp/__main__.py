"""
Drone Path Prediction Pipeline

Steps:
0. Extract telemetry (altitude, GPS) from subtitle stream
1. Sample frames (configurable step)
2. Compute optical flow between consecutive frames
3. Convert pixel motion → world coordinates (intrinsics + altitude)
4. Accumulate path with drift correction (optional: GPS anchors)
5. Visualize on map with GPS reference point
"""

import math
from dataclasses import dataclass
from typing import Iterator
import cv2
from pprint import pprint

import numpy as np

VIDEO_PATH = "/Users/agerasymchuk/private_repo/cv_nav/data/video1.MP4"


@dataclass(frozen=True)
class Frame:
    frame: np.ndarray
    index: int


def create_frame_reader(
    path: str, resize_coef: float = 0.5, stop: int | None = None
) -> Iterator[Frame]:
    step = 10
    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        print(f"could not open path: {path}")
        return

    frame_count = cap.get(cv2.CAP_PROP_FRAME_COUNT)

    current_frame = 0
    try:
        while current_frame < frame_count:
            if stop is not None and current_frame >= stop:
                break

            cap.set(cv2.CAP_PROP_POS_FRAMES, current_frame)
            success, frame = cap.read()
            if not success:
                print(f"unable to open frame position: {current_frame}")
                current_frame += step
                continue

            # paint gray
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

            # resize
            new_height, new_width = (
                int(resize_coef * dim_size) for dim_size in gray.shape
            )
            gray_resized = cv2.resize(gray, (new_width, new_height))
            print(f"new shape: {gray_resized.shape}")

            print(f"current position: {current_frame}")
            yield Frame(frame=gray_resized, index=current_frame)
            current_frame += step
    finally:
        cap.release()


def naïve_lk_optical_flow():
    frame_iterator = create_frame_reader(VIDEO_PATH, stop=None)
    # params for ShiTomasi corner detection
    feature_params = dict(maxCorners=100, qualityLevel=0.3, minDistance=7, blockSize=7)
    color = np.random.randint(0, 255, (100, 3))

    # Parameters for lucas kanade optical flow
    lk_params = dict(
        winSize=(15, 15),
        maxLevel=2,
        criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 10, 0.03),
    )

    first_frame = next(frame_iterator).frame
    mask = np.zeros_like(first_frame)

    p0 = cv2.goodFeaturesToTrack(first_frame, mask=None, **feature_params)

    for f in frame_iterator:
        frame = f.frame
        p1, st, err = cv2.calcOpticalFlowPyrLK(
            first_frame, frame, p0, None, **lk_params
        )
        if p1 is not None:
            good_new = p1[st == 1]
            good_old = p0[st == 1]
        else:
            print("no good matches found")
            continue

        # draw the tracks
        for i, (new, old) in enumerate(zip(good_new, good_old)):
            a, b = new.ravel()
            c, d = old.ravel()
            mask = cv2.line(
                mask, (int(a), int(b)), (int(c), int(d)), color[i].tolist(), 2
            )
            frame = cv2.circle(frame, (int(a), int(b)), 5, color[i].tolist(), -1)
        img = cv2.add(frame, mask)
        cv2.imshow("frame", img)
        k = cv2.waitKey(30) & 0xFF

        if k == 27:
            break

        first_frame = frame.copy()
        p0 = good_new.reshape(-1, 1, 2)

        print(f"frame: {f.frame.shape}, index: {f.index}")

    cv2.destroyAllWindows()


def calculate_intrinsic_matrix(
    image_width: int, image_height: int, fov_deg: int = 83
) -> np.ndarray:
    """
    Assuming square pixels, focal length equality: fx == fy
    | fx, 0, cx |
    | 0, fy, cy |
    | 0,  0,  1 |
    """
    diagonal_pixel = math.sqrt(image_width**2 + image_height**2)
    half_fov_radians = math.tan(math.radians(fov_deg / 2))
    focal_length = (diagonal_pixel / 2) / half_fov_radians
    cx = image_width / 2
    cy = image_height / 2
    return np.array(
        [
            [focal_length, 0, cx],
            [0, focal_length, cy],
            [0, 0, 1],
        ]
    )


def estimate_motion(
    frame1: np.ndarray,
    frame2: np.ndarray,
    K: np.ndarray,
    feature_params: dict,
    lk_params: dict,
):
    # 1. detect points to track on the frame 1
    points1 = cv2.goodFeaturesToTrack(frame1, mask=None, **feature_params)
    # 2. track
    points2, status, _ = cv2.calcOpticalFlowPyrLK(
        frame1, frame2, points1, nextPts=None, **lk_params
    )

    # 3. filter
    status = status.ravel()
    good1 = points1[status == 1]
    good2 = points2[status == 1]

    # 4. Geometry
    E, mask = cv2.findEssentialMat(good1, good2, K)
    _, R, t, _ = cv2.recoverPose(E, good1, good2, K)
    return R, t


def main():
    frame_iterator = create_frame_reader(VIDEO_PATH, stop=100)
    # params for ShiTomasi corner detection
    feature_params = dict(maxCorners=100, qualityLevel=0.3, minDistance=7, blockSize=7)

    current_position = np.zeros(3, dtype=np.float32)
    current_rotation = np.eye(3)
    drone_path = [current_position.copy()]

    # Parameters for lucas kanade optical flow
    lk_params = dict(
        winSize=(15, 15),
        maxLevel=2,
        criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 10, 0.03),
    )

    first_frame = next(frame_iterator).frame
    intrinsic_camera_matrix = calculate_intrinsic_matrix(
        first_frame.shape[1], first_frame.shape[0]
    )

    for f in frame_iterator:
        frame = f.frame
        R, t = estimate_motion(
            first_frame, frame, intrinsic_camera_matrix, feature_params, lk_params
        )
        print(f"index: {f.index}")
        print("R")
        pprint(R)
        print("t")
        pprint(t)

        current_rotation = current_rotation @ R
        current_position = current_position + current_rotation @ t.flatten()
        drone_path.append(current_position.copy())

        first_frame = frame

        print(f"frame: {f.frame.shape}, index: {f.index}")

    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
