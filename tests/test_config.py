import io
import unittest
from typing import cast

from FortiCfgParser import parse_file, FgtConfigRoot, section_table, FgtConfigTable
from tests import make_test_path


class TestConfig(unittest.TestCase):
    @staticmethod
    def _same_config(cfg1: list[str], cfg2: list[str]) -> bool:
        # Compare line by line for equality.  Leading and trailing spaces are not significant.
        return all(line1.strip() == line2.strip() for line1, line2 in zip(cfg1, cfg2))

    @staticmethod
    def _parse_and_compare(filename: str) -> bool:
        # Load and parse the configuration file
        config = parse_file(filename)

        # Write the configuration to a memory file
        output_buffer = io.StringIO()
        config.write(output_buffer, True)

        # Split as a list of strings
        text_config_1 = output_buffer.getvalue().split("\n")

        # Do the same with the file
        with open(filename, "r") as f:
            text_config_2 = f.read().split("\n")

        # and compare for equality
        return TestConfig._same_config(text_config_1, text_config_2)

    def test_config1(self) -> None:
        self.assertTrue(TestConfig._parse_and_compare(make_test_path("test1.conf")))

    def test_config2(self) -> None:
        self.assertTrue(TestConfig._parse_and_compare(make_test_path("test2.conf")))

    def test_config3(self) -> None:
        self.assertTrue(TestConfig._parse_and_compare(make_test_path("test3.conf")))

    def test_factory(self) -> None:
        class RootConfig(FgtConfigRoot):
            @section_table
            def firewall_address6(self) -> FgtConfigTable:  # type: ignore
                ...

        config = parse_file(make_test_path("test3.conf"), lambda _, cfg: RootConfig(cfg))
        config_root = cast(RootConfig, config.root)
        config_global = config_root.system_global()
        self.assertEqual("12", config_global.opt("timezone"))

        config_address = config_root.firewall_address6()
        self.assertEqual(
            "::/128",
            config_address.c_entry('none').opt('ip6')
            )

    def test_section(self) -> None:
        config = parse_file(make_test_path("test3.conf"))
        config_root = config.root

        for k, v in config_root.sections("router  bgp"):
            self.assertEqual("router bgp", k)

        section_count = 0
        for _, _ in config_root.sections('router'):
            section_count += 1
        self.assertEqual(8, section_count)
