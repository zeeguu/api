def find_last_reading_percentage(list, max_jump=10, max_total_update=40):
    """
        Takes a list of scroll events which are composed of tuples (second, % read) and outputs
        the last point the users has "read" to. This is an estimation, as it's impossible to 
        determine where exactly a user as stopped reading. E.g. a user might scroll to keep what 
        they are reading in the middle or read the entire screen and then scroll, etc...

        In the frontend, the percentage corresponds to where the viewport ends in relation to 
        an article. In other words, if the user viewport touches the end of the article, then it's 
        considered 100%. In smaller screens the text is wrapped, so it can result in a small 
        difference when going to a screen where the text fits the max-width.
            
        The method goes through the list of events and calculates how much % of the article the 
        user scrolls past in a second. If the user scrolls more than 10% in a second, it's not 
        considered that they have read that ammount of the article.

        However, let's say they scrolled quickly through the top image, and it's a rather small article,
        then if the speed is quite low, and they haven't scrolled more than 40% of the last point,
        then we consider that to be a valid update. 

        There's a grace of 5% meaning if the user as gotten to 95% of the article, then it's considered
        read.

        return percentage:float
    """
    max_until_now = 0
    for i in range(0, len(list)-1):
        t0, x0 = list[i]
        t1, x1 = list[i+1]
        v = abs(x1-x0) / (t1 - t0)
        max_point = max(x0, x1)
        # mean_point = sum([e[1] for e in list[i:i+2]]) / 2
        dif_update = abs(max_point - max_until_now)
        if v < max_jump and dif_update < max_total_update:
            max_until_now = max(max_until_now, max_point if max_point < 100 else 100)
    if max_until_now > 95:
        max_until_now = 100
    return round(max_until_now)/100