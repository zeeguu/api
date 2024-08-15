def find_last_reading_point(list, tolerance=2, max_jump=5, max_total_update=40):
    max_until_now = 0
    for i in range(0, len(list)-tolerance):
        t0, x0 = list[i]
        t1, x1 = list[i+tolerance-1]
        v = abs(x1-x0) / (t1 - t0)
        mean_point = sum([e[1] for e in list[i:(i+tolerance)]]) / tolerance
        dif_update = abs(mean_point - max_until_now)
        if v < max_jump and dif_update < max_total_update:
            max_until_now = max(max_until_now, mean_point if mean_point < 100 else 100)
    if max_until_now > 95:
        max_until_now = 100
    return round(max_until_now)