from xonsh.lib.collections import ChainDB


def test_dddi():
    a = {"a": {"a": {"a": 1}}}
    z = ChainDB(a)
    assert isinstance(z["a"], ChainDB)
    assert isinstance(z["a"]["a"], ChainDB)
    assert isinstance(z["a"]["a"]["a"], int)
    assert z["a"]["a"]["a"] + 1 == 2


def test_second_mapping():
    m1 = {"a": {"m": {"x": 0}}}
    m2 = {"a": {"m": {"y": 1}}}
    z = ChainDB(m1)
    z.maps.append(m2)
    assert isinstance(z["a"], ChainDB)
    assert isinstance(z["a"]["m"].maps, list)
    assert z["a"]["m"]["y"] == 1


def test_double_mapping():
    m1 = {"a": {"m": {"y": 0}}}
    m2 = {"a": {"m": {"y": 1}}}
    z = ChainDB(m1)
    z.maps.append(m2)
    assert isinstance(z["a"], ChainDB)
    assert isinstance(z["a"]["m"].maps, list)
    assert isinstance(z["a"]["m"]["y"], int)
    assert z["a"]["m"]["y"] == 1


def test_list_mapping():
    m1 = {"a": {"m": "x"}}
    m2 = {"a": {"m": "y"}}
    z = ChainDB(m1)
    z.maps.append(m2)
    assert isinstance(z["a"], ChainDB)
    assert isinstance(z["a"]["m"], str)
    assert z["a"]["m"] == "y"


def test_mixed_mapping():
    m1 = {"a": {"m": {"y": 1}}}
    m2 = {"a": {"m": 1}}
    z = ChainDB(m1)
    z.maps.append(m2)
    assert isinstance(z["a"], ChainDB)
    assert isinstance(z["a"]["m"], int)
    assert z["a"]["m"] == 1


def test_exactness():
    d = {"y": 1}
    m1 = {"a": {"m": d}}
    z = ChainDB(m1)
    assert isinstance(z["a"], ChainDB)
    assert isinstance(z["a"]["m"], ChainDB)
    assert isinstance(z["a"]["m"].maps[0], dict)
    assert d is z["a"]["m"].maps[0]


def test_exactness_setting():
    d = {"y": 1}
    m1 = {"a": {"m": d}}
    z = ChainDB(m1)
    e = {"z": 2}
    z["a"]["m"] = e
    assert isinstance(z["a"], ChainDB)
    assert isinstance(z["a"]["m"], ChainDB)
    assert isinstance(z["a"]["m"].maps[0], dict)
    assert e is z["a"]["m"].maps[0]


def test_exactness_setting_multi():
    d = "a"
    e = "b"
    m1 = {"a": {"m": d}}
    m2 = {"a": {"m": e}}
    z = ChainDB(m1)
    z.maps.append(m2)
    g = ("c",)
    z["a"]["m"] = g
    assert isinstance(z["a"], ChainDB)
    assert isinstance(z["a"]["m"], tuple)
    assert isinstance(z["a"].maps[0], dict)
    assert g is z["a"].maps[1]["m"]
    # We sent this to the first map not the last
    assert z["a"]["m"] is g


def test_exactness_setting_multi2():
    d = [1, 2]
    e = [3, 4]
    ee = [5, 6]
    m1 = {"a": {"m": d}}
    m2 = {"a": {"m": e, "mm": ee}}
    z = ChainDB(m1)
    z.maps.append(m2)
    g = [-1, -2]
    z["a"]["mm"] = g
    assert isinstance(z["a"], ChainDB)
    assert isinstance(z["a"]["m"], list)
    assert isinstance(z["a"].maps[0], dict)
    assert g is z["a"].maps[1]["mm"]
    assert z["a"]["mm"] is g
    assert z["a"]["m"] == [1, 2, 3, 4]


def test_exactness_setting_multi_novel():
    d = [1, 2]
    e = [3, 4]
    m1 = {"a": {"m": d}}
    m2 = {"a": {"m": e}}
    z = ChainDB(m1)
    z.maps.append(m2)
    g = [-1, -2]
    z["a"]["mm"] = g
    assert isinstance(z["a"], ChainDB)
    assert isinstance(z["a"]["m"], list)
    assert isinstance(z["a"].maps[0], dict)
    assert g is z["a"].maps[0]["mm"]
    assert g is z["a"]["mm"]


def test_dicts_in_lists():
    c = [{"m": 1}, {"n": 2}]
    d = [{"o": 3}, {"p": 4}]
    t = c + d
    m1 = {"a": {"b": c}}
    m2 = {"a": {"b": d}}
    z = ChainDB(m1)
    z.maps.append(m2)
    assert isinstance(z["a"], ChainDB)
    assert isinstance(z["a"]["b"], list)
    assert z["a"]["b"] == t
    assert c[0] is z["a"]["b"][0]
    assert c[1] is z["a"]["b"][1]
    assert d[0] is z["a"]["b"][2]
    assert d[1] is z["a"]["b"][3]


def test_dicts_in_lists_mutation():
    c = [{"m": 1}, {"n": 2}]
    d = [{"o": 3}, {"p": 4}]
    m1 = {"a": {"b": c}}
    m2 = {"a": {"b": d}}
    z = ChainDB(m1)
    z.maps.append(m2)
    append_list = z["a"]["b"]
    append_list.append({"hi": "world"})
    assert isinstance(append_list, list)
    assert z["a"]["b"] != append_list

    extend_list = z["a"]["b"]
    extend_list.extend([{"hi": "world"}, {"spam": "eggs"}])
    assert z["a"]["b"] != extend_list


def test_sets():
    m1 = {"a": {"b": {1, 2}}}
    m2 = {"a": {"b": {3, 4}}}
    z = ChainDB(m1)
    z.maps.append(m2)
    assert isinstance(z["a"]["b"], set)
    assert z["a"]["b"] == {1, 2, 3, 4}


def test_mixed_types():
    m1 = {"a": {"b": {1, 2}}}
    m2 = {"a": {"b": [3, 4]}}
    z = ChainDB(m1)
    z.maps.append(m2)
    assert isinstance(z["a"]["b"], list)
    assert z["a"]["b"] == [1, 2, 3, 4]
