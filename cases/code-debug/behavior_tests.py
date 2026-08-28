"""Hidden behavioral checks for the code-debug battery."""


def check(ns):
    if callable(ns.get("collect_evens")):
        f = ns["collect_evens"]
        return [f([1, 2, 4, 5]) == [2, 4], f([]) == [], f([-2, -1, 0]) == [-2, 0]]
    if callable(ns.get("area_of_rectangle")):
        f = ns["area_of_rectangle"]
        return [f(3, 4) == 12, f(0, 8) == 0, f(2.5, 4) == 10]
    if callable(ns.get("last_element")):
        f = ns["last_element"]
        return [f([1, 2, 3]) == 3, f(["x"]) == "x", f((4, 5)) == 5]
    if callable(ns.get("all_positive")):
        f = ns["all_positive"]
        return [f([1, 2, 3]) is True, f([1, 0, 3]) is False, f([]) is True]
    if callable(ns.get("multiplication_table")):
        f = ns["multiplication_table"]
        table = f(3)
        return [table == [[1, 2, 3], [2, 4, 6], [3, 6, 9]],
                len({id(row) for row in table}) == 3, f(0) == []]
    if callable(ns.get("take_items")):
        f = ns["take_items"]
        return [f([1, 2, 3]) == [1, 2, 3], f([1, 2, 3], 0) == [],
                f([1, 2, 3], 2) == [1, 2]]
    return [False, False, False]
