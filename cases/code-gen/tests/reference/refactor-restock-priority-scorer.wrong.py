def restock_priority(days_left, velocity, on_hand, shelf_cap, is_perishable):
    if days_left is None or velocity is None or on_hand is None or shelf_cap is None:
        return -1
    if days_left < 0 or velocity < 0 or on_hand < 0 or shelf_cap <= 0:
        return -1
    fill = on_hand / shelf_cap
    if days_left == 0:
        urg = 50
    elif days_left <= 2:
        urg = 40
    elif days_left <= 7:
        urg = 25
    elif days_left <= 30:
        urg = 10
    else:
        urg = 0
    if velocity >= 20:
        vel = 30
    elif velocity >= 10:
        vel = 20
    elif velocity >= 3:
        vel = 10
    elif velocity > 0:
        vel = 5
    else:
        vel = 0
    if fill < 0.1:
        stock = 20
    elif fill < 0.25:
        stock = 12
    elif fill < 0.5:
        stock = 6
    else:
        stock = 0
    score = urg + vel + stock
    if is_perishable and days_left <= 7:
        score += 15
    if on_hand >= shelf_cap and days_left >= 7 and not is_perishable:
        return 0
    return score
