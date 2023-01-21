#
# This file is part of FortiCfgParser -  A parser for FortiGate Configuration Files
#
# Copyright (C) 2022  Jean Noel Meurisse
# SPDX-License-Identifier: GPL-3.0-only
#

"""
    The implementation of a Fortigate configuration is organized as a hierarchy of classes.
    :py:class:``FgtConfigNode` is the root abstract base classes which represents a configuration
    node in the configuration object tree.

    Class hierarchy :
                            FgtConfigNode
                                  |
                                  |
                 -----------------+------------------
                 |                |                 |
            FgtConfigSet    FgtConfigUnset     FgtConfigBody
                                                      |
                                                      |
                                              --------+--------
                                              |               |
                                        FgtConfigTable   FgtConfigObject
"""

from abc import ABC, abstractmethod
from collections import deque
from types import FunctionType
from typing import Any, Union, Optional, Callable, TextIO, Iterator, final, TypeVar

FgtConfigToken = str
""" A token in a config file. A token is a sequence of characters. """

FgtConfigTokens = list[FgtConfigToken]
""" A list of tokens, the list can be empty. """

FgtConfigItem = tuple[str, 'FgtConfigNode']
""" Represents the parameter name and the associated configuration node. """

FgtConfigStack = deque[FgtConfigItem]
""" A stack of configuration items.  
This stack is generated during the traversal of the configuration tree. """

FgtConfigTraverseCallback = Callable[[bool, FgtConfigItem, FgtConfigStack, Any], None]
""" Callback function called during the traversal of the configuration tree. 
The function is called with 4 arguments :
    * a flag indicating if we enter or leave a node,
    * the current node,
    * the stack of parent nodes,
    * optional user data.
"""

FgtConfigFilterCallback = Callable[[FgtConfigItem, FgtConfigStack, Any], bool]
""" Callback function called from `FgtConfig.make_config` method.  
This callback offers the caller to filter some config from the configuration tree. The function is
called with 3 arguments :
    * the current node,
    * the stack of parent nodes,
    * user data.
The filter function must return a boolean.  The config_text function does not output the 
current node if the filter returns True.
"""


def uqs(arg: str) -> str:
    """ Return an unquoted string.

    :param arg: a string
    :return: the unquoted string
    """
    if len(arg) < 2:
        res = arg
    elif arg[0] != '"' or arg[-1] != '"':
        res = arg
    else:
        res = arg.replace('\\"', '"').replace('\\\\', '\\')[1:-1]

    return res


def qus(arg: str) -> str:
    """ Return a quoted string. Backslashes and quotes are properly escaped with a backslash.

    :param arg: a string
    :return: the quoted string
    """
    return '"{}"'.format(arg.replace('\\', '\\\\').replace('"', '\\"'))


class FgtConfigNode(ABC):
    """ Represents a configuration node in the configuration object tree.

    A configuration node can be a SET command, an UNSET command or a CONFIG command.  A derived
    class exists for each object type.  A :py:class:`FgtConfigNode` is always accessed through a
    dictionary that maps a configuration parameter to the object.  The configuration parameter is
    never  stored in the object itself.
    """

    @abstractmethod
    def traverse(self,
                 key: str,
                 fn: FgtConfigTraverseCallback,
                 parents: FgtConfigStack,
                 data: Any
                 ) -> None:
        """ Recursively traverse a configuration object tree and call `fn` on each node.

        This function allows to traverse over the generated object tree created by
        `FgtParser.parse`.  The function calls `fn` callback before and after a CONFIG object is
        traversed.

        Note: It is the caller responsibility to call this method with the parameter name that was
        used to map this entry in a dictionary.

        :param key: the configuration parameter name of this object in the dictionary
        :param fn: a callback called on each node.
        :param parents: a stack of parents.  Each entry in the stack is a tuple (str, FgtConfigNode)
        :param data: user data passed to the callback.

        """


class FgtConfigDict(dict[str, FgtConfigNode]):
    """ A dictionary of configuration node children. """

    def skeys(self) -> list[str]:
        """ Return a sorted list of all keys in this dictionary. """
        return sorted(self.keys(), key=lambda s: s.lower())


class FgtConfigBody(FgtConfigNode, FgtConfigDict, ABC):
    """ An abstract base class for a CONFIG table or a CONFIG object. """

    def traverse(self,
                 key: str,
                 fn: FgtConfigTraverseCallback,
                 parents: FgtConfigStack,
                 data: Any
                 ) -> None:
        # … enter the config section
        fn(True, (key, self), parents, data)
        parents.append((key, self))

        # ... enumerate all items in this dictionary
        for item_key, item_value in self.items():
            item_value.traverse(item_key, fn, parents, data)

        # … leave the config section
        parents.pop()
        fn(False, (key, self), parents, data)

    def walk(self, key: str, delimiter: str = "/") -> Iterator[FgtConfigItem]:
        """ Recursively yield all descendant config nodes in the tree including this node.
        The method uses BFS method to visit every node of the tree.

        :param key: the configuration parameter name of this object in the dictionary.
        :param delimiter : the path delimiter
        :return: a pair consisting of the path (concatenated keys) and the node.
        """
        pending: deque[FgtConfigItem] = deque([(key, self)])
        while len(pending) > 0:
            path, node = pending.popleft()
            if isinstance(node, (FgtConfigObject, FgtConfigTable)):
                pending.extend([(path + delimiter + k, v) for k, v in node.items()])
                yield path, node
            elif isinstance(node, (FgtConfigSet, FgtConfigUnset)):
                yield path, node
            else:
                raise TypeError()


class FgtConfigObject(FgtConfigBody):
    """ Represents a CONFIG command containing multiple SET, UNSET commands or
    CONFIG subcommands.  A subcommand can be obtained using one of the following
    methods :

    * conf_obj['param']
    * conf_obj.get('param')
    * conf_obj.opt('param')
    * conf_obj.param

    In the following example::

        set vdom "root"
        set ip 192.168.254.99 255.255.255.0
        set allowaccess ping https
        set alias "mngt"
        config example
        end

    The parameter can be obtained in the following manner :

    * object['ip'], object.get('ip') or object.ip returns  ['192.168.254.99', '255.255.255.0']
    * object['vdom'], object.get('vdom') returns ['"root"']
    * object.opt['vdom'] or object.vdom returns '"root"'
    * object['example'] or object.get('example') returns a FgtConfigNode

    The class also provides methods for retrieving typed nodes :

    * conf_obj.c_object('param')    returns a `FgtConfigObject`
    * conf_obj.c_table('param')     returns a `FgtConfigTable`
    * conf_obj.c_set('param')       returns a `FgtConfigSet`

    """

    def c_table(self, key: str, default: Optional['FgtConfigTable'] = None) -> 'FgtConfigTable':
        """ A convenient method that returns a config table.

         The method raises a TypeError exception if the resulting config node is not of type
         `FgtConfigTable` and raises a KeyError if the `key` is not found in this dictionary
         unless a default value was specified.
         """
        value = self[key] if default is None else self.get(key, default)
        if not isinstance(value, FgtConfigTable):
            raise TypeError(f"'{key}' is not of type FgtConfigTable")
        return value

    def c_object(self, key: str, default: Optional['FgtConfigObject'] = None) -> 'FgtConfigObject':
        """ A convenient method that returns a config object.

         The method raises a TypeError exception if the resulting config node is not of type
         `FgtConfigObject` and raises a KeyError if the `key` is not found in this dictionary
         unless a default value was specified.
         """
        value = self[key] if default is None else self.get(key, default)
        if not isinstance(value, FgtConfigObject):
            raise TypeError(f"'{key}' is not of type FgtConfigObject")
        return value

    def c_set(self, key: str, default: Optional['FgtConfigSet'] = None) -> 'FgtConfigSet':
        """ A convenient method that returns a config object.

         The method raises a TypeError exception if the resulting config node is not of type
         `FgtConfigSet` and raises a KeyError if the `key` is not found in this dictionary
         unless a default value was specified.
         """
        value = self[key] if default is None else self.get(key, default)
        if not isinstance(value, FgtConfigSet):
            raise TypeError(f"'{key}' is not of type FgtConfigSet")
        return value

    def opt(self, key: str, default: Optional[str] = None) -> str:
        """ return the value of a simple SET command.  A simple SET command
        defines a configuration parameter with a single value such as in

        |       set status enable.

        :param key: name of the parameter
        :param default: default value
        :return: the value of the parameter or the `default` value if the parameter is not defined
        in the CONFIG object.
        """
        try:
            config_set = self.c_set(key)
            if len(config_set) > 1:
                raise ValueError("opt method is available only on simple set command")
        except KeyError as e:
            if default is None:
                raise e
            return default

        return config_set[0]

    def same(self, key: str, value: str, default: Optional[str] = None) -> bool:
        """ compare the parameter value with the given value. """
        return self.opt(key, default) == value

    def __getattr__(self, key: str) -> FgtConfigNode:
        """ return the parameter value.  This method allows the use of object.param
        syntax equivalent to object.get('param')
        """
        if key not in self.keys():
            return super().__getattribute__(key)

        attribute = self.get(key)
        if attribute is None:
            raise AttributeError(key)
        return attribute


class FgtConfigTable(FgtConfigBody):
    """ Represents a CONFIG command containing multiple EDIT commands """

    def c_entry(self, key: Union[str, int]) -> FgtConfigObject:
        """ A convenient method that returns a config object.

            The method raises a TypeError exception if the resulting config node is not of type
            `FgtConfigObject` and raises a KeyError if the `key` is not found in this dictionary
            unless a default value was specified.

            With the following configuration table :
            config test
                    edit "opt1"
                    next
                    edit "opt2"
                    next
            end
            self.c_entry('opt1') returns the first entry and is equivalent to self['"opt1"]

            With the following configuration table :
            config test
                    edit 1
                    next
                    edit 2
                    next
            end
            self.c_entry('1') returns the first entry and is equivalent to self['1']
        """
        if isinstance(key, int):
            value = self[str(key)]
        elif isinstance(key, str):
            value = self[qus(key)]
        else:
            raise TypeError("Invalid key type")

        if isinstance(value, FgtConfigObject):
            return value

        raise TypeError(f"subcommand {key} is not a FgtConfigObject")


@final
class FgtConfigSet(FgtConfigNode):
    """ Represents a SET command. """

    def __init__(self, parameters: FgtConfigTokens) -> None:
        self._parameters = parameters

    def __getitem__(self, index: int) -> FgtConfigToken:
        return self._parameters[index]

    def __setitem__(self, index: int, value: Any) -> None:
        self._parameters[index] = value

    def __repr__(self) -> str:
        return repr(self._parameters)

    def __len__(self) -> int:
        return len(self._parameters)

    @property
    def params(self) -> FgtConfigTokens:
        """ Return the parameters of this SET command. """
        return self._parameters

    def traverse(self,
                 key: str,
                 fn: FgtConfigTraverseCallback,
                 parents: FgtConfigStack,
                 data: Any
                 ) -> None:
        fn(True, (key, self), parents, data)


@final
class FgtConfigUnset(FgtConfigNode):
    """ Represents an UNSET command. """

    def traverse(self,
                 key: str,
                 fn: FgtConfigTraverseCallback,
                 parents: FgtConfigStack,
                 data: Any
                 ) -> None:
        fn(True, (key, self), parents, data)

    def __len__(self) -> int:
        return 0


T = TypeVar('T', bound='FgtConfigRoot')


def section_object(config_key: Callable[[T], FgtConfigObject]) -> Callable[[T], FgtConfigObject]:
    """ A decorator indicating a configuration object section.

    This is a convenience function to simplify creating a function that loads a
    configuration object.

    Example:

    |   @section_object
    |   def system_global(self): ...
    |   is equivalent to
    |   def system_global(self):
    |       return self.get('system global', FgtConfigObject())

    """
    if isinstance(config_key, FunctionType):
        key = config_key.__name__.replace("_", " ")
        return lambda c: c.c_object(key)

    raise TypeError()


def section_table(config_key: Callable[[T], FgtConfigTable]) -> Callable[[T], FgtConfigTable]:
    """ A decorator indicating a configuration table section.

    This is a convenience function to simplify creating a function that loads a
    configuration table.

    """
    if isinstance(config_key, FunctionType):
        key = config_key.__name__.replace("_", " ")
        return lambda c: c.c_table(key)

    raise TypeError()


_FgtConfigSection = Union[FgtConfigTable, FgtConfigObject]


class FgtConfigRoot(FgtConfigObject):
    def sections(self,
                 partial_key: Optional[str] = None
                 ) -> Iterator[tuple[str, _FgtConfigSection]]:
        """ Return all sections in the root configuration. """
        if partial_key is None:
            for k, v in self.items():
                if isinstance(v, (FgtConfigTable, FgtConfigObject)):
                    yield k, v
        else:
            partial_key_parts = partial_key.split()
            for k, v in self.items():
                if isinstance(v, (FgtConfigTable, FgtConfigObject)):
                    k_parts = k.split()
                    same = partial_key_parts == k_parts[:len(partial_key_parts)]
                    if same:
                        yield k, v

    def traverse(self,
                 key: str,
                 fn: FgtConfigTraverseCallback,
                 parents: FgtConfigStack,
                 data: Any
                 ) -> None:
        for item_key, item_value in self.items():
            item_value.traverse(item_key, fn, parents, data)

    @section_object
    def system_global(self) -> FgtConfigObject:             # type: ignore
        ...

    @section_table
    def system_interface(self) -> FgtConfigTable:           # type: ignore
        ...

    @section_table
    def system_admin(self) -> FgtConfigTable:               # type: ignore
        ...

    @section_object
    def system_dns(self) -> FgtConfigObject:                # type: ignore
        ...

    @section_table
    def user_local(self) -> FgtConfigTable:                 # type: ignore
        ...

    @section_table
    def user_group(self) -> FgtConfigTable:                 # type: ignore
        ...

    @section_table
    def firewall_address(self) -> FgtConfigTable:           # type: ignore
        ...

    @section_table
    def firewall_addrgrp(self) -> FgtConfigTable:           # type: ignore
        ...

    @section_table
    def firewall_vip(self) -> FgtConfigTable:               # type: ignore
        ...

    @section_table
    def firewall_vipgrp(self) -> FgtConfigTable:            # type: ignore
        ...

    @section_table
    def firewall_service_custom(self) -> FgtConfigTable:    # type: ignore
        ...

    @section_table
    def firewall_service_group(self) -> FgtConfigTable:     # type: ignore
        ...

    @section_table
    def firewall_policy(self) -> FgtConfigTable:            # type: ignore
        ...

    @section_table
    def router_static(self) -> FgtConfigTable:              # type: ignore
        ...


@final
class FgtConfigComments(FgtConfigTokens):
    def _config_version(self) -> list[str]:
        version = ["?-?"]
        for comment in self:
            if comment.startswith("#config-version="):
                version = comment[16:].split(':')
        return version

    @property
    def version(self) -> str:
        """ Return the FortiOS version. """
        config_version = self._config_version()[0]
        return config_version[config_version.index('-') + 1:]

    @property
    def model(self) -> str:
        """ Return the firewall model. """
        config_version = self._config_version()[0]
        return config_version[0:config_version.index('-')]


@final
class FgtConfig(object):
    """ A Fortigate configuration.

    This object is created by calling `FgtParser.parse()`.

    """

    def __init__(self,
                 comments: FgtConfigComments,
                 root: FgtConfigRoot,
                 vdoms: dict[str, FgtConfigRoot]
                 ) -> None:
        """
        :param comments: A list of comments found at the start of the configuration file
        :param root: a dictionary of config objects and tables
        :param vdoms: a dictionary of root config for each vdom.  This dictionay must be empty if
        vdoms are not used.
        """
        if not all(isinstance(v, (FgtConfigObject, FgtConfigTable)) for v in root.values()):
            raise ValueError()

        self._comments: FgtConfigComments = comments
        self._root: FgtConfigRoot = root
        self._vdoms: dict[str, FgtConfigRoot] = vdoms
        self._indent: int = 4

    @property
    def comments(self) -> FgtConfigComments:
        """ Return the collection of comments """
        return self._comments

    @property
    def has_vdom(self) -> bool:
        """ Return true if the firewall is configured with VDOMs"""
        return len(self._vdoms) > 0

    @property
    def root(self) -> FgtConfigRoot:
        """ Return the root configuration.

         The function returns all config objects/tables under 'config global' section
         in a multiple VDOMs configuration and the whole configuration (all config
         objects/tables) if VDOMs are not configured.
         """
        return self._root

    @property
    def vdoms(self) -> dict[str, FgtConfigRoot]:
        """ Return a dictionary of VDOMs. """
        return self._vdoms

    def make_config(self,
                    item_filter: Optional[FgtConfigFilterCallback] = None,
                    data: Optional[Any] = None
                    ) -> list[str]:
        """ Return the configuration as a list of string.
        Joining this list creates the initial configuration.

        :param item_filter: an optional filtering callback. This function is called for each node
                            in the configuration tree.  The node is skipped if the callback returns
                            true.
        :param data: optional data passed to the item_filter callback.
        """

        def append_entry(begin_of_section: bool,
                         item: FgtConfigItem,
                         parents: FgtConfigStack,
                         output_list: list[str]
                         ) -> None:

            # check if we skip this item
            if item_filter and not item_filter(item, parents, data):
                return

            # extract key, value from the given item
            key = item[0]
            value = item[1]

            if isinstance(value, FgtConfigSet):
                line = f"set {key} {' '.join(value.params)}"
            elif isinstance(value, FgtConfigUnset):
                line = f"unset {key}"
            elif isinstance(value, (FgtConfigTable, FgtConfigObject)):
                if len(parents) == 0 or isinstance(parents[-1][1], FgtConfigObject):
                    line = f"config {key}" if begin_of_section else "end"
                elif len(parents) > 0 or isinstance(parents[-1][1], FgtConfigTable):
                    line = f"edit {key}" if begin_of_section else "next"
                else:
                    raise ValueError()
            else:
                raise ValueError()

            # create indentation spaces to prefix the line
            spaces: str = ' ' * (len(parents) * self._indent)

            # append it to the output list
            output_list.append(spaces + line)

        output: list[str] = []
        if self.has_vdom:
            output.append('')
            output.append('config vdom')
            for k in self.vdoms.keys():
                output.append('edit ' + k)
                output.append('next')
            output.append('end')
            output.append('')
            output.append('config global')
            self.root.traverse('', append_entry, deque(), output)
            output.append('end')
            output.append('')
            for k, v in self.vdoms.items():
                output.append('config vdom')
                output.append('edit ' + k)
                v.traverse('', append_entry, deque(), output)
                output.append('end')
                output.append('')
        else:
            self.root.traverse('', append_entry, deque(), output)
        return output

    def __repr__(self) -> str:
        return "\n".join(self.make_config())

    def write(self,
              file: TextIO,
              include_comments: bool,
              item_filter: Optional[FgtConfigFilterCallback] = None,
              data: Optional[Any] = None
              ) -> None:
        """ Write the configuration to a file.

        :param file: the output file.
        :param include_comments: output configuration comments when true.
        :param item_filter: an optional filtering callback. This function is called for each
                            node in the configuration tree.  The node is skipped if the callback
                            returns true.
        :param data: optional data passed to the item_filter callback.
        """
        if include_comments and len(self.comments) > 0:
            file.write("\n".join(self.comments))
            file.write("\n")
        file.write("\n".join(self.make_config(item_filter, data)))
        file.write("\n")
