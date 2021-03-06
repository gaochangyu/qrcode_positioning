# coding=utf-8
from Queue import Queue
from collections import deque

import cv2
import numpy as np
import math

import time

import zbar


def createLineIterator(P1, P2, img):
    """
    Produces and array that consists of the coordinates and intensities of each pixel in a line between two points

    Parameters:
        -P1: a numpy array that consists of the coordinate of the first point (x,y)
        -P2: a numpy array that consists of the coordinate of the second point (x,y)
        -img: the image being processed

    Returns:
        -it: a numpy array that consists of the coordinates and intensities of each pixel in the radii (shape: [numPixels, 3], row = [x,y,intensity])
    """
    # define local variables for readability
    imageH = img.shape[0]
    imageW = img.shape[1]
    P1X = P1[0]
    P1Y = P1[1]
    P2X = P2[0]
    P2Y = P2[1]

    # difference and absolute difference between points
    # used to calculate slope and relative location between points
    dX = P2X - P1X
    dY = P2Y - P1Y
    dXa = np.abs(dX)
    dYa = np.abs(dY)

    # predefine numpy array for output based on distance between points
    itbuffer = np.empty(shape=(np.maximum(dYa, dXa), 3), dtype=np.float32)
    itbuffer.fill(np.nan)

    # Obtain coordinates along the line using a form of Bresenham's algorithm
    negY = P1Y > P2Y
    negX = P1X > P2X
    if P1X == P2X:  # vertical line segment
        itbuffer[:, 0] = P1X
        if negY:
            itbuffer[:, 1] = np.arange(P1Y - 1, P1Y - dYa - 1, -1)
        else:
            itbuffer[:, 1] = np.arange(P1Y + 1, P1Y + dYa + 1)
    elif P1Y == P2Y:  # horizontal line segment
        itbuffer[:, 1] = P1Y
        if negX:
            itbuffer[:, 0] = np.arange(P1X - 1, P1X - dXa - 1, -1)
        else:
            itbuffer[:, 0] = np.arange(P1X + 1, P1X + dXa + 1)
    else:  # diagonal line segment
        steepSlope = dYa > dXa
        if steepSlope:
            slope = dX.astype(np.float32) / dY.astype(np.float32)
            if negY:
                itbuffer[:, 1] = np.arange(P1Y - 1, P1Y - dYa - 1, -1)
            else:
                itbuffer[:, 1] = np.arange(P1Y + 1, P1Y + dYa + 1)
            itbuffer[:, 0] = (slope * (itbuffer[:, 1] - P1Y)).astype(np.int) + P1X
        else:
            slope = dY.astype(np.float32) / dX.astype(np.float32)
            if negX:
                itbuffer[:, 0] = np.arange(P1X - 1, P1X - dXa - 1, -1)
            else:
                itbuffer[:, 0] = np.arange(P1X + 1, P1X + dXa + 1)
            itbuffer[:, 1] = (slope * (itbuffer[:, 0] - P1X)).astype(np.int) + P1Y

    # Remove points outside of image
    colX = itbuffer[:, 0]
    colY = itbuffer[:, 1]
    itbuffer = itbuffer[(colX >= 0) & (colY >= 0) & (colX < imageW) & (colY < imageH)]

    # Get intensities from img ndarray
    itbuffer[:, 2] = img[itbuffer[:, 1].astype(np.uint), itbuffer[:, 0].astype(np.uint)]

    return itbuffer


def cv_distance(p, q):
    """
    calculate the distance between two opencv points
    :param p: one 2-dimension numpy array
    :param q: another 2-dimension numpy array
    :return: return the distance between two points
    """
    return int(math.sqrt(pow((p[0] - q[0]), 2) + pow((p[1] - q[1]), 2)))


def draw_short_connections(a, b):
    """
    draw the two shortest connection lines between two Position Detection Pattern box corners
    :param a: Position Detection Pattern box corner array a
    :param b: Position Detection Pattern box corner array b
    :return: no return
    """
    # 存储 ab 数组里最短的两点的组合
    s1_ab = ()
    s2_ab = ()
    # 存储 ab 数组里最短的两点的距离，用于比较
    s1 = np.iinfo('i').max
    s2 = s1
    for ai in a:
        for bi in b:
            d = cv_distance(ai, bi)
            if d < s2:
                if d < s1:
                    s1_ab, s2_ab = (ai, bi), s1_ab
                    s1, s2 = d, s1
                else:
                    s2_ab = (ai, bi)
                    s2 = d
    a1, a2 = s1_ab[0], s2_ab[0]
    b1, b2 = s1_ab[1], s2_ab[1]
    a1 = (a1[0] + (a2[0] - a1[0]) * 1 / 14, a1[1] + (a2[1] - a1[1]) * 1 / 14)
    b1 = (b1[0] + (b2[0] - b1[0]) * 1 / 14, b1[1] + (b2[1] - b1[1]) * 1 / 14)
    a2 = (a2[0] + (a1[0] - a2[0]) * 1 / 14, a2[1] + (a1[1] - a2[1]) * 1 / 14)
    b2 = (b2[0] + (b1[0] - b2[0]) * 1 / 14, b2[1] + (b1[1] - b2[1]) * 1 / 14)

    # 将最短的两个线画出来
    cv2.line(draw_img, a1, b1, (0, 0, 255), 1)
    cv2.line(draw_img, a2, b2, (0, 0, 255), 1)


def check(a, b, binary_img, threshold):
    """
    check whether the two input Position Detection Pattern box a and b are in one qr code
    :param a: Position Detection Pattern box corner array a
    :param b: Position Detection Pattern box corner array b
    :param binary_img: the binary image containing the qrcode
    :return: boolean judgement, true if the two Position Detection Patterns are in one qr code
    """
    # 存储 ab 数组里最短的两点的组合
    s1_ab = ()
    s2_ab = ()
    # 存储 ab 数组里最短的两点的距离，用于比较
    s1 = np.iinfo('i').max
    s2 = s1
    for ai in a:
        for bi in b:
            d = cv_distance(ai, bi)
            if d < s2:
                if d < s1:
                    s1_ab, s2_ab = (ai, bi), s1_ab
                    s1, s2 = d, s1
                else:
                    s2_ab = (ai, bi)
                    s2 = d
    a1, a2 = s1_ab[0], s2_ab[0]
    b1, b2 = s1_ab[1], s2_ab[1]
    a1 = (a1[0] + (a2[0] - a1[0]) * 1 / 14, a1[1] + (a2[1] - a1[1]) * 1 / 14)
    b1 = (b1[0] + (b2[0] - b1[0]) * 1 / 14, b1[1] + (b2[1] - b1[1]) * 1 / 14)
    a2 = (a2[0] + (a1[0] - a2[0]) * 1 / 14, a2[1] + (a1[1] - a2[1]) * 1 / 14)
    b2 = (b2[0] + (b1[0] - b2[0]) * 1 / 14, b2[1] + (b1[1] - b2[1]) * 1 / 14)

    return is_timing_pattern(createLineIterator(a1, b1, binary_img)[:, 2], threshold) or is_timing_pattern(
        createLineIterator(a2, b2, binary_img)[:, 2], threshold)


def is_timing_pattern(line, threshold):
    """
    to judge wether the input line is a timing pattern
    :param line: input line
    :return: true if the line is a timing pattern
    """

    #ignore too short line
    if len(line) < 10:
        return False

    # 除去开头结尾的白色像素点
    #while line[0] != 0:
    #    line = line[1:]
    #while line[-1] != 0:
    #    line = line[:-1]
    # 计数连续的黑白像素点
    c = []
    count = 1
    l = line[0]
    for p in line[1:]:
        if p == l:
            count += 1
        else:
            # 排除一些太小的线段，这些可能是噪声
            if count > 2:
                c.append(count)
            count = 1
        l = p
    if count > 1:
        c.append(count)
    # 如果黑白间隔太少，直接排除
    if len(c) < 5:
        return False
    # 计算方差，根据离散程度判断是否是 Timing Pattern
    #threshold = 5
    return np.var(c) < threshold


def find_contour_corner(contour):
    """
    find the Position Detection Pattern contour corners
    :param contour: the contour end points in a ndarray
    :return: if the algorithm succeed, it returns the corners of the contour in a ndarray, or it returns the corners of the minimum area rectangle containing the pattern
    """
    i = 0
    # temp_result = np.array([[0,0]])
    corners = np.array([[0, 0]])
    temp_result = Queue()
    while i < len(contour) - 1:
        if contour[i].item(0) == contour[i + 1].item(0):
            # temp_result = np.append(temp_result, contour[i:i+1], axis=0)
            temp_result.put(contour[i], False)
            temp_result.put(contour[i + 1], False)
            i += 2
        else:
            i += 1

    temp_result.put(temp_result.get())

    threshold = 10
    while not temp_result.empty():
        temp_a = temp_result.get()
        temp_b = temp_result.get()
        if cv_distance(temp_a[0], temp_b[0]) > threshold:
            corners = np.append(corners, temp_a, axis=0)
            corners = np.append(corners, temp_b, axis=0)

    if corners.size == 10:
        return corners[1:]
    else:
        rect = cv2.minAreaRect(contour)
        box = cv2.boxPoints(rect)
        box = np.int0(box)
        return box


def is_valid_symbol(symbol_string):
    return True


def scan(boxes, gray_img, zbar_scanner, bi_threshold, timing_pattern_threshold):
    """
    this function scan the image and select one area that contains a valid qr code
    :param boxes:
    :return:
    """
    he_img = cv2.equalizeHist(gray_img)

    pixels = np.array([])
    #meter the average intensity of the boxes

    if len(boxes) >0:

        for box in boxes:
            box_x, box_y, box_w, box_h = cv2.boundingRect(np.array(box))
            temp_img = gray_img[box_y:box_y+box_h, box_x:box_x + box_w]
            pixels = np.append(pixels, temp_img)
        bi_threshold = np.average(pixels)

    th, bi_img = cv2.threshold(he_img, bi_threshold, 255, cv2.THRESH_BINARY)

    cv2.imshow("binary", bi_img)
    cv2.waitKey(1)
    current_state = "ZERO"  # state includes "ZERO", "ONE", "TWO", "MORE","FAIL"
    next_state = "ZERO"
    qr_boxes_candidate = deque()
    success = False
    result_symbol = ""
    candidate_i = deque()

    while True:
        current_state = next_state

        if current_state == "ZERO":
            if len(boxes) < 3:
                next_state = "FAIL"
                continue
            candidate_i.clear()
            candidate_i.append(0)
            for i in range(1, len(boxes)):
                if check(boxes[0], boxes[i], bi_img, timing_pattern_threshold):
                    candidate_i.append(i)

            valid_count = len(candidate_i)
            if valid_count == 1:
                boxes = boxes[1:]
                next_state = "ZERO"
            elif valid_count == 2:
                qr_boxes_candidate.append(boxes[candidate_i[0]])
                qr_boxes_candidate.append(boxes[candidate_i[1]])
                boxes = np.delete(boxes, candidate_i,axis=0)
                next_state = "ONE"
            elif valid_count == 3:
                qr_boxes_candidate.append(boxes[candidate_i[0]])
                qr_boxes_candidate.append(boxes[candidate_i[1]])
                qr_boxes_candidate.append(boxes[candidate_i[2]])
                boxes = np.delete(boxes, candidate_i,axis=0)
                next_state = "TWO"
            else:
                for x in candidate_i:
                    qr_boxes_candidate.append(boxes[x])
                boxes = np.delete(boxes, candidate_i,axis=0)
                next_state = "MORE"
        elif current_state == "ONE":
            if len(boxes) == 0:
                next_state = "FAIL"
                continue
            candidate_i.clear()
            for i in range(0, len(boxes)):
                if check(qr_boxes_candidate[1], boxes[i], bi_img, timing_pattern_threshold):
                    candidate_i.append(i)
            valid_count = len(candidate_i)
            if valid_count == 0:
                qr_boxes_candidate.clear()
                next_state = "ZERO"
            elif valid_count == 1:
                qr_boxes_candidate.append(boxes[candidate_i[0]])
                boxes = np.delete(boxes, candidate_i, axis=0)
                next_state = "TWO"
            else:
                for x in candidate_i:
                    qr_boxes_candidate.append(boxes[x])
                boxes = np.delete(boxes, candidate_i,axis=0)
                next_state = "MORE"
        elif current_state == "TWO":
            x, y, w, h = cv2.boundingRect(np.array(qr_boxes_candidate).reshape((12, 2)))
            x -= 30
            y -= 30
            w += 30
            h += 30
            if x <0:
                x = 0
            if y < 0:
                y = 0

            qr_zone_img = gray_img[y:y + h, x:x + w]
            zbar_img = zbar.Image(w, h, 'Y800', qr_zone_img.tostring())
            zbar_scanner.scan(zbar_img)
            for symbol in zbar_img:
                if is_valid_symbol(symbol):
                    success = True
                    result_symbol = symbol
            del zbar_img
            if(success):
                break
            else:
                qr_boxes_candidate.clear()
                next_state = "ZERO"
        elif current_state == "MORE":
            success = False
            result_symbol = ""
            break
        elif current_state == "FAIL":
            # handle exceptional situations
            success = False
            result_symbol = ""
            break
        else:
            pass

    return [success, result_symbol]

def nothing(x):
    pass


if __name__ == "__main__":

    cv2.namedWindow('image')
    cv2.createTrackbar('canny_1','image',200,1000,nothing)
    cv2.createTrackbar('canny_2','image',600,1000,nothing)
    cv2.createTrackbar('canny_a','image',3,50,nothing)
    cv2.createTrackbar('gau_k_size','image',1,50,nothing)
    cv2.createTrackbar('gau_sigma','image',2,50,nothing)
    cv2.createTrackbar('bi_threshold','image',150,255,nothing)
    cv2.createTrackbar('timing_threshold', 'image', 5, 50, nothing)
    cap = cv2.VideoCapture(0)

    if not cap.isOpened():
        print "failed to open the camera"
        exit(-1)

    cap.set(3, 640)
    cap.set(4, 480)

    scanner = zbar.ImageScanner()

    scanner.parse_config("disable")
    #scanner.enable_cache() # do not enable cache here
    scanner.parse_config("qrcode.enable")

    while True:

        ret, img = cap.read()
        cv2.imshow("image", img)
        cv2.waitKey(1)
        if not ret:
            continue



        start = time.clock()

        #img = cv2.imread("/home/edward/workspace/qrcode_positioning/resources/640/4.jpg")
        # #cv2.imshow("test", img)
        # cv2.waitKey()

        # pre-processings for the input images




        threshold_1 = cv2.getTrackbarPos('canny_1', 'image')
        threshold_2 = cv2.getTrackbarPos('canny_2', 'image')
        apeture = cv2.getTrackbarPos('canny_a','image')/ 2 * 2 + 1 # rounded to a odd number
        gau_k_size = cv2.getTrackbarPos('gau_k_size','image')/2 * 2 +1 # rounded to a odd number
        gau_sig = cv2.getTrackbarPos('gau_sigma','image') # rounded to a odd number

        img_gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        img_he = cv2.equalizeHist(img_gray)

        img_gb = cv2.GaussianBlur(img_he, (gau_k_size, gau_k_size), gau_sig)

        edges = cv2.Canny(img_gb, threshold_1, threshold_2, apeture)



        # 使用形态学闭合操作有效弥合一些边缘图中二位码定位点的缺口
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
        closing = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, kernel)

        cv2.imshow("edges", edges)
        cv2.waitKey(1)

        cv2.imshow("closing", closing)
        cv2.waitKey(1)

        # find contours in the image

        img_fc, contours, hierarchy = cv2.findContours(edges, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)

        if len(contours) == 0:
            continue


        hierarchy = hierarchy[0]
        found = []

        # find the qr code positioning patterns in the image
        for i in range(len(contours)):
            k = i
            c = 0
            while hierarchy[k][2] != -1:
                k = hierarchy[k][2]
                c += 1
            if c >= 5:
                found.append(i)

        # draw the found qr code positioning pattern contours
        img_dc = img.copy()
        for i in found:
            cv2.drawContours(img_dc, contours, i, (0, 255, 0), 1)
        cv2.imshow("contour", img_dc)
        cv2.waitKey(1)

        # find the contour corners and draw in the image
        draw_img = img.copy()
        for i in found:
            box = find_contour_corner(contours[i])
            cv2.drawContours(draw_img, [box], 0, (0, 0, 255), 2)
        cv2.imshow("draw_img", draw_img)
        cv2.waitKey(1)

        # find the contour corners and store the corners in boxes
        boxes = []
        for i in found:
            box = find_contour_corner(contours[i])
            box = map(tuple, box)
            boxes.append(box)

        bi_threshold = cv2.getTrackbarPos("bi_threshold","image")
        timing_pattern_threshold = cv2.getTrackbarPos("timing_threshold","image")
        success, symbol = scan(boxes, img_gb, scanner,bi_threshold, timing_pattern_threshold)

        if success:
            print symbol.data
            end = time.clock()
            print str((end - start) * 1000) + "ms"
        else:
            pass
            #print "scanning failed."


