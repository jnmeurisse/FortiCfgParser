import unittest
from collections import deque

from FortiCfgParser import parse_config, FgtConfig, FgtConfigObject, FgtConfigTable, FgtConfigSet, FgtConfigRoot
from FortiCfgParser._parser import FgtConfigSyntaxError


class TestParser(unittest.TestCase):

    def test_empty(self):
        config_text = ""
        config = parse_config(config_text)

        self.assertEqual(len(config.make_config()), 0)

    def test_simple(self):
        config_text = "config test\nend"
        config = parse_config(config_text)

        self.assertMultiLineEqual(str(config), config_text)

    def test_simple_types(self):
        config_text = "config test\nend"
        config = parse_config(config_text)

        self.assertIsInstance(config, FgtConfig)
        self.assertIsInstance(config.root.get('test'), FgtConfigObject)

    def test_types_1(self):
        config_text = \
            """
                config test
                    edit 1
                        set parameter1 value1
                        config subconfig
                            edit 1
                                set parameter2 value2
                            next
                        end
                    next
                    edit 2
                    next
                end
            """
        config = parse_config(config_text)

        self.assertTrue(isinstance(config, FgtConfig))

        conf_table = config.root.c_table('test')
        self.assertIsInstance(conf_table, FgtConfigTable)
        self.assertEqual(len(conf_table), 2)
        self.assertListEqual(list(conf_table.keys()), ['1', '2'])
        self.assertEqual(len(conf_table), 2)
        self.assertIsInstance(conf_table.c_entry(1), FgtConfigObject)
        self.assertIsInstance(conf_table.c_entry(2), FgtConfigObject)

        entry_1 = conf_table.c_entry(1)
        self.assertIsInstance(entry_1, FgtConfigObject)
        self.assertListEqual(entry_1.c_set('parameter1').params, ['value1'])
        self.assertEqual(conf_table.c_entry(1).opt('parameter1'), 'value1')

        entry_2 = conf_table.c_entry(2)
        self.assertEqual(len(entry_2), 0)

    def test_types_2(self):
        config_text = \
            """
                config test
                    edit "opt1"
                        set parameter1 value1 "value2" value3
                        config subconfig1
                            edit 1
                                set parameter2 value2
                            next
                        end
                        config subconfig2
                            edit "ABC"
                                set parameter3 value3
                            next
                        end
                    next
                    edit "opt2"
                    next
                end
            """
        config = parse_config(config_text)

        self.assertTrue(isinstance(config, FgtConfig))

        conf_root = config.root.c_table('test')
        self.assertIsInstance(conf_root, FgtConfigTable)
        self.assertEqual(len(conf_root), 2)
        self.assertListEqual(list(conf_root.keys()), ['"opt1"', '"opt2"'])

        self.assertIsInstance(conf_root.get('"opt1"'), FgtConfigObject)
        opt1 = conf_root.c_entry('opt1')
        self.assertIsInstance(opt1, FgtConfigObject)
        self.assertEqual(opt1, conf_root.get('"opt1"'))

        self.assertEqual(len(opt1), 3)
        self.assertIsInstance(opt1.get('parameter1'), FgtConfigSet)
        self.assertListEqual(opt1.c_set('parameter1').params, ['value1', '"value2"', 'value3'])
        self.assertEqual(opt1.c_table('subconfig1').c_entry(1).opt('parameter2'), 'value2')
        self.assertEqual(opt1.c_table('subconfig2').c_entry('ABC').opt('parameter3'), 'value3')

        self.assertIsInstance(conf_root.get('"opt2"'), FgtConfigObject)
        opt2 = conf_root.c_entry('opt2')
        self.assertEqual(len(opt2), 0)

    def test_comments_1(self):
        config_text = \
            """
                # comment 1 "test"
                
                # comment 2
                # comment 3
                
                config test
                    edit "opt1"
                    next

                    edit "opt2"
                    next
                end
            """
        config = parse_config(config_text)
        self.assertEqual(len(config.comments), 3)
        self.assertListEqual(config.comments, ['# comment 1 "test"', '# comment 2', '# comment 3'])
        conf_root = config.root.get('test')
        self.assertIsInstance(conf_root, FgtConfigTable)

    def test_comments_2(self):
        config_text = \
            """
                #config-version=FGT60E-5.04-FW-build1111-161216:opmode=0:vdom=0:user=admin
                config test
                end
            """
        config = parse_config(config_text)
        self.assertEqual(config.comments.version, '5.04-FW-build1111-161216')
        self.assertEqual(config.comments.model, 'FGT60E')

    def test_comments_3(self):
        config_text = ""
        config = parse_config(config_text)
        self.assertEqual(config.comments.version, '?')
        self.assertEqual(config.comments.model, '?')

    def test_section_1(self):
        config_text = \
            """
                #config-version=FGT60E-5.04-FW-build1111-161216:opmode=0:vdom=0:user=admin
                config system interface
                    edit "wan1"
                    next
                end
            """
        config = parse_config(config_text)
        self.assertIsInstance(config.root.system_interface(), FgtConfigTable)

    def test_loop(self):
        config_text = "config test\nend"
        for test_index in range(10):
            self.assertTrue(str(parse_config(config_text) == config_text))

    def test_vdom(self):
        """ test a vdom """
        config_text = \
            """
                #config-version=FGT60E-5.04-FW-build1111-161216:opmode=0:vdom=1:user=admin
                config vdom
                    edit root
                end
                config global
                end
            """
        config = parse_config(config_text)
        self.assertTrue(config.has_vdom)
        self.assertIsInstance(config.root, FgtConfigRoot)
        self.assertIsInstance(config.vdoms['root'], FgtConfigRoot)

    def test_walk(self):
        config_text = \
            """
                config level1.1
                    config level2.1.1
                    end
                    config level2.1.2
                        set param1 value1
                    end
                    config level2.1.3
                    end
                end
                config level1.2
                    config level2.2.1
                    end
                    config level2.2.2
                    end
                    config level2.2.3
                    end                
                end
                config level1.3
                    config level2.3.1
                        config level3.3.1
                            set param1 value1
                            set param2 value2
                        end
                    end
                end
            """
        paths = ["root",
                 "root/level1.1",
                 "root/level1.2",
                 "root/level1.3",
                 "root/level1.1/level2.1.1",
                 "root/level1.1/level2.1.2",
                 "root/level1.1/level2.1.3",
                 "root/level1.2/level2.2.1",
                 "root/level1.2/level2.2.2",
                 "root/level1.2/level2.2.3",
                 "root/level1.3/level2.3.1",
                 "root/level1.1/level2.1.2/param1",
                 "root/level1.3/level2.3.1/level3.3.1",
                 "root/level1.3/level2.3.1/level3.3.1/param1",
                 "root/level1.3/level2.3.1/level3.3.1/param2"]

        config = parse_config(config_text)
        nodes = []
        for node in config.root.walk("root"):
            nodes.append(node[0])
        self.assertListEqual(paths, nodes)

    def test_travers(self):
        config_text = \
            """
                config level1.1
                    config level2.1.1
                    end
                    config level2.1.2
                        set param1 value1
                    end
                    config level2.1.3
                    end
                end
                config level1.2
                    config level2.2.1
                    end
                    config level2.2.2
                    end
                    config level2.2.3
                    end                
                end
                config level1.3
                    config level2.3.1
                        config level3.3.1
                            set param1 value1
                            set param2 value2
                        end
                    end
                end
            """

        def cb(enter, node, stack, data):
            if enter:
                print(node[0], node[1])
            pass

        config = parse_config(config_text)
        root = config.root
        root.traverse("root", cb, deque(), None)

    def test_error_1(self):
        config_text = "config test end"
        with self.assertRaises(FgtConfigSyntaxError):
            parse_config(config_text)

    def test_error_2(self):
        config_text = "abc"
        with self.assertRaises(FgtConfigSyntaxError):
            parse_config(config_text)

    def test_error_3(self):
        config_text = \
            """
                config test
                    edit "opt1"
                    edit "opt2"
                    next
                end
            """
        with self.assertRaises(FgtConfigSyntaxError):
            parse_config(config_text)

    def test_error_4(self):
        config_text = \
            """
                config test
                    edit "opt1
                    next
                    edit "opt2"
                    next
                end
            """
        with self.assertRaises(FgtConfigSyntaxError):
            parse_config(config_text)

    def test_error_5(self):
        config_text = \
            """
                config test
                    set param1 value1
                    set param2 value2
                    set param3 value3
                    config param4
                    end
                end
            """
        config_root = parse_config(config_text).root
        self.assertTrue(config_root.c_object('test').same('param1', 'value1'))
        self.assertTrue(config_root.c_object('test').same('param2', 'value2'))
        self.assertTrue(config_root.c_object('test').same('param3', 'value3'))
        with self.assertRaises(TypeError):
            config_root.c_object('test').opt('param4')
        self.assertTrue(config_root.c_object('test').same('param5', 'value5', 'value5'))
