PTS = [
    (1, 0, 0),
    (1, 1, 0),
    (0, 1, 0),
    (0, 1, 1),
    (0, 0, 1),
    (1, 0, 1),
]

def interpolate(pt_a, pt_b, wt_a):
    return tuple(a * wt_a + b * (1 - wt_a) for a, b in zip(pt_a, pt_b))

def scale(pt, scal):
    return tuple(int(a * scal) for a in pt)

def color_wheel(idx, steps):
    steps_per_point = steps / len(PTS)

    cur_point = 0

    pt_a = None

    incr = idx % steps_per_point
    if incr == 0 or pt_a is None:
        cur_point += 1
        if cur_point >= len(PTS):
            # wrap around
            pt_a = PTS[cur_point - 1]
            pt_b = PTS[0]
        else:
            pt_a = PTS[cur_point - 1]
            pt_b = PTS[cur_point]

    wt_a = float(steps_per_point - incr) / steps_per_point
    return interpolate(pt_a, pt_b, wt_a)
