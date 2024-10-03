def remove_duplicates_keeping_order(l: list):
    seen_elements = set()
    duplicates_removed_l = []
    for ele in l:
        if ele not in seen_elements:
            seen_elements.add(ele)
            duplicates_removed_l.append(ele)
    return duplicates_removed_l
