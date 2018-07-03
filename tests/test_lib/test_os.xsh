from xonsh.lib.os import indir

def test_indir(source_path):
    assert ![pwd].output.strip() != source_path
    with indir(source_path):
        assert ![pwd].output.strip() == source_path
    assert ![pwd].output.strip() != source_path
