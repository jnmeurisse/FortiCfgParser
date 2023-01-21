from os.path import join, dirname


def make_test_path(filename):
    return join(dirname(__file__), "config", filename)
