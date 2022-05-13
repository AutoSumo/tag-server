import math
import json

from pupil_apriltags import Detector
import cv2
import asyncio
import websockets


connections = set()


def in_ellipse(x_p, y_p, x_c, y_c, a, b, angle):
    ellipse = (((((math.cos(angle) * (x_p - x_c)) + (math.sin(angle) * (y_p - y_c))) ** 2) / (a**2)) +
               ((((math.sin(angle) * (x_p - x_c)) - (math.cos(angle) * (y_p - y_c))) ** 2) / (b**2)))
    return ellipse <= 1


async def connect(websocket):
    connections.add(websocket)
    print('Got connection!')
    try:
        await websocket.wait_closed()
    finally:
        connections.remove(websocket)


def main():
    print('Starting video capture')
    vid = cv2.VideoCapture(0)
    at_detector = Detector(families='tag36h11',
                           nthreads=1,
                           quad_decimate=1.0,
                           quad_sigma=0.0,
                           refine_edges=1,
                           decode_sharpening=0.80,
                           debug=0)
    width = int(vid.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(vid.get(cv2.CAP_PROP_FRAME_HEIGHT))

    while True:
        ret, frame = vid.read()
        gray_image = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        tag_size_cm = 20.5

        focal_length = (1, 1)
        camera_center = (1, 1)

        tags = at_detector.detect(gray_image, estimate_tag_pose=True,
                                  camera_params=[focal_length[0], focal_length[1], camera_center[0], camera_center[1]],
                                  tag_size=(tag_size_cm / 100))

        corners = [None, None, None, None]
        corner_ids = [1, 2, 3, 4]

        for r in tags:
            if corner_ids.count(r.tag_id) > 0:
                corners[corner_ids.index(r.tag_id)] = r
                # extract the bounding box (x, y)-coordinates for the AprilTag
                # and convert each of the (x, y)-coordinate pairs to integers
                (ptA, ptB, ptC, ptD) = r.corners
                ptB = (int(ptB[0]), int(ptB[1]))
                ptC = (int(ptC[0]), int(ptC[1]))
                ptD = (int(ptD[0]), int(ptD[1]))
                ptA = (int(ptA[0]), int(ptA[1]))
                # draw the bounding box of the AprilTag detection
                cv2.line(frame, ptA, ptB, (0, 255, 0), 2)
                cv2.line(frame, ptB, ptC, (0, 255, 0), 2)
                cv2.line(frame, ptC, ptD, (0, 255, 0), 2)
                cv2.line(frame, ptD, ptA, (0, 255, 0), 2)
                # draw the center (x, y)-coordinates of the AprilTag
                (cX, cY) = (int(r.center[0]), int(r.center[1]))
                cv2.circle(frame, (cX, cY), 5, (0, 0, 255), -1)
                # draw the tag family on the image
                tagFamily = r.tag_family.decode("utf-8")
                cv2.putText(frame, str(r.tag_id), (cX, cY),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

        if corners.count(None) > 0:
            cv2.putText(frame, 'Corners missing', (5, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
        else:
            cv2.putText(frame, 'All corners found', (5, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
            cv2.line(frame, (int(corners[0].center[0]), int(corners[0].center[1])),
                            (int(corners[1].center[0]), int(corners[1].center[1])), (0, 0, 0), 2)
            cv2.line(frame, (int(corners[1].center[0]), int(corners[1].center[1])),
                            (int(corners[2].center[0]), int(corners[2].center[1])), (0, 0, 0), 2)
            cv2.line(frame, (int(corners[2].center[0]), int(corners[2].center[1])),
                             (int(corners[3].center[0]), int(corners[3].center[1])), (0, 0, 0), 2)
            cv2.line(frame, (int(corners[3].center[0]), int(corners[3].center[1])),
                             (int(corners[0].center[0]), int(corners[0].center[1])), (0, 0, 0), 2)

            midpoint = (int(sum([corners[x].center[0] for x in range(0, 4)])/4), int(sum([corners[x].center[1] for x in range(0, 4)])/4))
            cv2.circle(frame, midpoint, 4, (0, 0, 255))

            center_left = (int((corners[0].center[0]+corners[3].center[0])/2), int((corners[0].center[1]+corners[3].center[1])/2))
            center_right = (int((corners[1].center[0]+corners[2].center[0])/2), int((corners[1].center[1]+corners[2].center[1])/2))
            center_top = (int((corners[2].center[0]+corners[3].center[0])/2), int((corners[2].center[1]+corners[3].center[1])/2))
            center_bottom = (int((corners[0].center[0]+corners[1].center[0])/2), int((corners[0].center[1]+corners[1].center[1])/2))

            cv2.line(frame, center_left, center_right, (0, 0, 0), 1)
            cv2.line(frame, center_top, center_bottom, (0, 0, 0), 1)

            e_height = int(math.sqrt((abs(center_top[0]-center_bottom[0])**2) + (abs(center_top[1]-center_bottom[1])**2)) / 2)
            e_width = int(math.sqrt((abs(center_left[0]-center_right[0])**2) + (abs(center_left[1]-center_right[1])**2)) / 2)
            angle = math.atan2(center_right[0]-midpoint[0], center_right[1]-midpoint[1])

            cv2.ellipse(frame, midpoint, (e_width, e_height), angle, 0, 360, (255, 0, 0))

            #for x in range(0, width, 5):
            #    for y in range(0, height, 5):
            #        color = (0, 255, 0) if in_ellipse(x, y, midpoint[0], midpoint[1], e_width, e_height, angle) else (0, 0, 255)
            #        cv2.circle(frame, (x, y), 3, color)

            extra = []

            for t in tags:
                if corner_ids.count(t.tag_id) > 0:
                    continue

                in_ell = in_ellipse(int(t.center[0]), int(t.center[1]), midpoint[0], midpoint[1], e_width, e_height, angle)
                color = (0, 255, 0) if in_ell else (0, 0, 255)

                extra.append({'x': int(t.center[0]), 'y': int(t.center[1]), 'in': in_ell, 'id': t.tag_id})

                # extract the bounding box (x, y)-coordinates for the AprilTag
                # and convert each of the (x, y)-coordinate pairs to integers
                (ptA, ptB, ptC, ptD) = r.corners
                ptB = (int(ptB[0]), int(ptB[1]))
                ptC = (int(ptC[0]), int(ptC[1]))
                ptD = (int(ptD[0]), int(ptD[1]))
                ptA = (int(ptA[0]), int(ptA[1]))
                # draw the bounding box of the AprilTag detection
                cv2.line(frame, ptA, ptB, color, 2)
                cv2.line(frame, ptB, ptC, color, 2)
                cv2.line(frame, ptC, ptD, color, 2)
                cv2.line(frame, ptD, ptA, color, 2)
                # draw the center (x, y)-coordinates of the AprilTag
                (cX, cY) = (int(r.center[0]), int(r.center[1]))
                cv2.circle(frame, (cX, cY), 5, (0, 0, 255), -1)
                # draw the tag family on the image
                tagFamily = r.tag_family.decode("utf-8")
                cv2.putText(frame, str(r.tag_id), (cX, cY),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

        websockets.broadcast(connections, json.dumps(extra))

        cv2.imshow('Frame', frame)

        # q to quit
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break


async def main_async(loop):
    # None uses the default executor (ThreadPoolExecutor)
    await loop.run_in_executor(None, main)


if __name__ == '__main__':
    start_server = websockets.serve(connect, 'localhost', 7844)
    asyncio.get_event_loop().run_until_complete(start_server)
    asyncio.get_event_loop().run_until_complete(main_async(asyncio.get_event_loop()))
    asyncio.get_event_loop().run_forever()
