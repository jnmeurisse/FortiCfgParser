<h1 align="center">A FortiGate configuration file parser</h1>

# Description
This package provides a non-validating FortiGate configuration file parser. 

A FortiGate configuration file contains a set of command lines. A command line 
consists of a command word (`set`, `unset` or `config`), usually followed by 
configuration data.  The `set` command is used to configure a parameter, 
the `unset` command is used to reset a parameter to its default value and the
`config` command is used to introduce a configuration  object such as in the 
example 1 here after or a configuration table as in the example 2.
#### Example 1 : a config object
    config system global
        set admin-server-cert "my-cert"
        set admintimeout 30
        set alias "FGT60EXX123456"
        set gui-certificates enable
    end
#### Example 2 : a config table
    config system interface
        edit "wan1"
            set vdom "root"
            set ip 182.168.10.1 255.255.255.0
            ...
        next
        edit "wan2"
            ...
        next
    end

## Parser
`FgtConfigParser.parse_file` parses a FortiGate backup file and returns 
an instance of `FgtConfig` that holds the configuration.  The main 
properties of this object are
- `has_vdom`: True if VDOMs are configured.
- `root`: provides an instance of `FgtConfigRoot` that contains all config 
objects/tables under *config global* section in a multiple VDOMs 
(has_vdom property is True) configuration and the whole configuration (all config 
objects/tables) if VDOMs are not configured (has_vdom property is False).
- `vdoms`: provides a dictionary that maps VDOM name to an instance of 
`FgtConfigRoot`.

After parsing, the firewall configuration is stored in a hierarchy of objects 
derived from `FgtConfigNode` class:
- `FgtConfigSetCmd` class represents a `set` command 
- `FgtConfigUnsetCmd` class represents a `unset` command
- `FgtConfigObject` class represents a `config` object (see example 1)
- `FgtConfigTable` class represents a `config` table (see example 2)

`FgtConfigObject` and `FgtConfigTable` are dictionaries that allows the 
retrieval of sub configuration nodes.  `FgtConfigSetCmd` and `FgtConfigUnsetCommand` are 
the leaf in the object hierarchy.

`FgtConfigRoot` is a derived class of `FgtConfigObject`.


# Examples

```
    config = FgtConfigParser.parse_file("example1.conf")
    root = config.root
    print(root.get('system global').admintimeout)
```


# Installation
