#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause
# Copyright (c) 2025 ikwzm

import sys
import os
import re
import argparse
from kconfiglib import Kconfig, expr_value, \
                       Symbol, Choice, MENU, COMMENT, BOOL, TRISTATE, STRING, INT, HEX, UNKNOWN

class DefConfigExplainer:

    class Node:
        def __init__(self, menu_node, parent, level):
            self.menu_node = menu_node
            self.parent    = parent
            self.level     = level
            self.next      = None
            self.list      = None
            self.defined   = False
            self.config    = None
            self.is_symbol = menu_node.item.__class__ is Symbol
            self.is_choice = menu_node.item.__class__ is Choice
            self.is_menu   = menu_node.item is MENU or menu_node.is_menuconfig is True
            self.prompt    = menu_node.prompt[0] if menu_node.prompt else None
            self.help      = menu_node.help if hasattr(menu_node, "help") else None

    _OPTIONS = {
        "warnings"              : (False , "print warning"),
        "stderr_warnings"       : (False , "print warning to stderr"),
        "undef_warnings"        : (False , "print undef warning"),
        "override_warnings"     : (False , "print override warning"),
        "redun_warnings"        : (False , "print redun warning"),
        "print_first_level"     : (1     , "print first level"),
        "print_max_column"      : (80    , "print max column"),
        "print_comment"         : (False , "print prompt with comment"),
        "print_help"            : (False , "print prompt with help"),
        "print_location"        : (False , "print prompt with location"),
        "print_orig_config"     : (False , "print prompt with original config"),
        "print_choice_item"     : (False , "print choice item"),
        "print_same_level_item" : (False , "print same level as defined config"),
        "prompt_indent_char"    : ('#'   , None),
        "separator_indent_char" : ('#'   , None),
        "info_indent_char"      : ('#'   , None),
        "separator_char_list"   : ([]    , None),
        "separator_format"      : ("{separator_indent} {separator_line}", None),
        "prompt_format"         : ("#{separator}\n#{prompt_indent} {prompt}\n#{separator}", None),
        "help_format"           : ("#{info_indent} help\n{help}\n#{info_indent}", None),
        "help_line_format"      : ("#{info_indent}     {help_line}", None),
        "orig_config_format"    : ("#{info_indent} {config}", None),
        "location_format"       : ("#{info_indent} {filename} : {linenr}\n#{info_indent}", None),
        "menu_end_format"       : ("#{prompt_indent} end of {prompt}\n", None),
    }

    @classmethod
    def options(cls):
        options_dict = {}
        for name, value_list in cls._OPTIONS.items():
            value = value_list[0]
            if value_list[1] is None:
                _help = name.replace("_", " ")
            else:
                _help = value_list[1]
            options_dict[name] = {"name": name, "value": value, "help": _help}
        return options_dict
    
    def __init__(self, kconfig_file, options={}):
        self.kconf = Kconfig(kconfig_file)

        self.options = DefConfigExplainer.options()
        self.update_options(options)
        self.update_kconf_option()
        
        self.comment_match = re.compile(r"^#").match
        self.defined_config_list = []
        self.defined_config_dict = {}
        self.max_level           = 0
        self.level_size          = 0
        self.top_node            = None
        self.generate_print_format()

    def update_kconf_option(self):
        for key in ["warnings","stderr_warnings","undef_warnings","override_warnings","redun_warnings"]:
            if self.get_option(key, False) is True:
                getattr(self.kconf, f"enable_{key}")()
            else:
                getattr(self.kconf, f"disable_{key}")()

    def get_option(self, name, default=None):
        if name in self.options:
            return self.options[name]["value"]
        else:
            return default

    def update_options(self, options={}):
        for name, value in options.items():
            self.update_option(name, value)

    def update_option(self, name, value):
        name = name.replace("-", "_")
        old_value = self.get_option(name)
        new_value = None
        if old_value is None:
            raise KeyError(f"{name} is not option name")
        if old_value.__class__ == list:
            if   value is None:
                new_value = []
            elif value.__class__ == list:
                new_value = value
            else:
                new_value = old_value + [value]
        if old_value.__class__ == bool:
            if   value.__class__ == bool:
                new_value = value
            elif value.__class__ == str:
                if   value.lower() in ["y", "yes", "true" ]:
                    new_value = True
                elif value.lower() in ["n", "no" , "false"]:
                    new_value = False
            elif old_value.__class__ == value.__class__:
               new_value = value
        if new_value is None:
            raise ValueError(f"{value} is invalid option value")
        self.options[name]["value"] = new_value

    def preload_config_files(self, defconfig_files = [], verbose = None):
        replace = True
        for defconfig_file in defconfig_files:
            self.kconf.load_config(defconfig_file, replace, verbose)
            replace = False

    def load_config_files(self, defconfig_files = [], replace = True, verbose = None):
        for defconfig_file in defconfig_files:
            self.kconf.load_config(defconfig_file, replace, verbose)
        for defconfig_file in defconfig_files:
            self.load_config(defconfig_file)
        self.max_level  = 0
        self.top_node   = self.make_node_tree(self.kconf.top_node, None, 0)
        self.level_size = self.max_level + 1
        self.generate_print_format()
        
    def generate_print_format(self, options={}):
        self.update_options(options)
        self.print_comment            = self.get_option("print_comment")
        self.print_help               = self.get_option("print_help")
        self.print_orig_config        = self.get_option("print_orig_config")
        self.print_location           = self.get_option("print_location")
        self.print_choice_item        = self.get_option("print_choice_item")
        self.print_same_level_item    = self.get_option("print_same_level_item")

        _print_first_level            = self.get_option("print_first_level")
        _print_max_column             = self.get_option("print_max_column")
        _prompt_indent_char           = self.get_option("prompt_indent_char")
        _separator_indent_char        = self.get_option("separator_indent_char")
        _separator_char_list          = self.get_option("separator_char_list")
        _separator_format             = self.get_option("separator_format")
        _info_indent_char             = self.get_option("info_indent_char")
        _prompt_format                = self.get_option("prompt_format")
        _help_format                  = self.get_option("help_format")
        _help_line_format             = self.get_option("help_line_format")
        _orig_config_format           = self.get_option("orig_config_format")
        _location_format              = self.get_option("location_format")
        _menu_end_format              = self.get_option("menu_end_format")

        separator_char_list           = ['']*self.level_size
        separator_char_list[_print_first_level:_print_first_level+len(_separator_char_list)] = _separator_char_list
        self.print_first_level        = _print_first_level
        self.print_prompt_format      = []
        self.print_menu_end_format    = []
        self.print_location_format    = []
        self.print_help_format        = []
        self.print_help_line_format   = []
        self.print_orig_config_format = []
        for level in range(self.level_size):
            format_params = {
                "prompt_indent"    : _prompt_indent_char    * level,
                "separator_indent" : _separator_indent_char * level,
                "info_indent"      : _info_indent_char      * level,
                "separator_line"   : separator_char_list[level]*(_print_max_column),
                "prompt"           : "{prompt}",
                "help"             : "{help}",
                "help_line"        : "{help_line}",
                "config"           : "{config}",
                "filename"         : "{filename}",
                "linenr"           : "{linenr}",
            }
            separator = _separator_format.format(**format_params)
            format_params["separator"] = separator[:_print_max_column-1]
            prompt_format      = _prompt_format.format(**format_params)
            menu_end_format    = _menu_end_format.format(**format_params)
            help_format        = _help_format.format(**format_params)
            help_line_format   = _help_line_format.format(**format_params)
            location_format    = _location_format.format(**format_params)
            orig_config_format = _orig_config_format.format(**format_params)
            self.print_prompt_format.append(prompt_format)
            self.print_menu_end_format.append(menu_end_format)
            self.print_help_format.append(help_format)
            self.print_help_line_format.append(help_line_format)
            self.print_orig_config_format.append(orig_config_format)
            self.print_location_format.append(location_format)
        
    def print(self, params={}, file=sys.stdout):
        if not params:
            self.generate_print_format(params)
        if self.print_first_level == 1:
            self.print_node_tree(self.top_node.list, False, file)
        else:
            self.print_node_tree(self.top_node     , False, file)
            
    def print_node_tree(self, node, force_print, file):
        if self.print_same_level_item is True:
            found_defined = False
            all_symbol    = True
            walk_node     = node
            while walk_node:
                if walk_node.defined:
                    found_defined = True
                if not walk_node.is_symbol:
                    all_symbol = False
                walk_node = walk_node.next
            if found_defined is True and all_symbol is True:
                force_print = True
        while node:
            if node.defined is True or force_print is True:
                if node.is_menu:
                    self.print_menu_node(  node, force_print, file)
                else:
                    self.print_config_node(node, force_print, file)
            node = node.next

    def print_menu_node(self, node, force_print, file):
        need_new_line = False
        if node.prompt:
            self.print_node_prompt(node, file)
            need_new_line = True
            if self.print_help and node.help:
                self.print_node_help(node, file)
            if self.print_location:
                self.print_node_location(node, file)
        if self.print_comment:
            self.print_node_comment(node, file)
        if node.config or self.print_orig_config or force_print:
            self.print_node_config(node, file)
            need_new_line = True
        if need_new_line is True:
            print("", file=file)
        if node.list:
            print_choice_item = self.print_choice_item and node.is_choice
            self.print_node_tree(node.list, print_choice_item, file)
        if node.prompt:
            format = self.print_menu_end_format[node.level]
            print(format.format(prompt=node.prompt), file=file)
        
    def print_config_node(self, node, force_print, file):
        need_new_line = False
        if node.prompt:
            self.print_node_prompt(node, file)
            need_new_line = True
            if self.print_help and node.help:
                self.print_node_help(node, file)
            if self.print_location:
                self.print_node_location(node, file)
        if self.print_comment:
            self.print_node_comment(node, file)
        if node.config or self.print_orig_config or force_print:
            self.print_node_config(node, file)
            need_new_line = True
        if need_new_line is True:
            print("", file=file)
        if node.list:
            self.print_node_tree(node.list, False, file)

    def print_node_config(self, node, file):
        if node.config:
            print(node.config["line"] , file=file)
        elif node.is_symbol:
            sym    = node.menu_node.item
            config = sym.config_string.rstrip().lstrip("# ")
            format = self.print_orig_config_format[node.level]
            print(format.format(config=config), file=file)
        
    def print_node_prompt(self, node, file):
        format = self.print_prompt_format[node.level]
        print(format.format(prompt=node.prompt), file=file)
        
    def print_node_help(self, node, file):
        help_lines       = []
        help_line_format = self.print_help_line_format[node.level]
        help_format      = self.print_help_format[node.level]
        for help_line in node.help.splitlines():
            help_lines.append(help_line_format.format(help_line=help_line))
        print(help_format.format(help="\n".join(help_lines)), file=file)
        
    def print_node_location(self, node, file):
        filename = node.menu_node.filename
        linenr   = node.menu_node.linenr
        format   = self.print_location_format[node.level]
        print(format.format(filename=filename,linenr=linenr), file=file)
        
    def print_node_comment(self, node, file):
        if node.config:
            comment = node.config["comment"]
            print(comment)

    def make_node_tree(self, menu_node, parent_node, level):
        first_node = None
        prev_node  = None
        while menu_node:
            curr_node = DefConfigExplainer.Node(menu_node, parent_node, level)
            ## print(f"===> {curr_node.menu_node}")
            ## print(f"    visibility {curr_node.menu_node.visibility}")
            ## print(f"    referenced {curr_node.menu_node.referenced}")
            ## print(f"    class      {menu_node.item.__class__}")
            ## print(f"    dep        {expr_value(curr_node.menu_node.dep)}")
            if expr_value(curr_node.menu_node.dep) > 0:
                if isinstance(menu_node.item, Symbol) or isinstance(menu_node.item, Choice) :
                    name = menu_node.item.name
                    ## print(f"    name {name}")
                    if name in self.defined_config_dict:
                        curr_node.defined = True
                        curr_node.config  = self.defined_config_dict[name]
                        parent = parent_node
                        while parent and parent.defined is False:
                            parent.defined = True
                            parent = parent.parent
                    ## print(f"    defined {curr_node.defined}")
            if menu_node.list:
                curr_node.list = self.make_node_tree(menu_node.list, curr_node, level+1)
            if prev_node:
                prev_node.next = curr_node
            else:
                first_node = curr_node
            prev_node = curr_node
            menu_node = menu_node.next
        if self.max_level < level:
            self.max_level = level
        return first_node
        
    def load_config(self, defconfig_file):
        config_list   = []
        comment_match = self.comment_match
        set_match     = self.kconf._set_match
        unset_match   = self.kconf._unset_match
        get_sym       = self.kconf.syms.get
        with self.kconf._open_config(defconfig_file) as f:
            comment_lines = []
            for line_num, line in enumerate(f, 1):
                line = line.rstrip()
                match = set_match(line)
                if match:
                    name, val = match.groups()
                    sym = get_sym(name)
                    ## print(f"===> CONFIG_{name}={val}")
                    config_info = {"name": name, "line": line}
                    if sym and sym.nodes:
                        config_info["symbol"] = sym
                    config_info["comment"] = "\n".join(comment_lines)
                    comment_lines = []
                    config_list.append(config_info)
                    continue
                match = unset_match(line)
                if match:
                    name = match.group(1)
                    sym = get_sym(name)
                    ## print(f"===> CONFIG_{name} is unset")
                    config_info = {"name": name, "line": line}
                    if sym and sym.nodes:
                        config_info["symbol"] = sym
                    config_info["comment"] = "\n".join(comment_lines)
                    comment_lines = []
                    config_list.append(config_info)
                    continue
                match = comment_match(line)
                if match:
                    comment_lines.append(line)
                else:
                    comment_lines = []
        self.defined_config_list.extend(config_list)
        for config_info in config_list:
            name = config_info["name"]
            self.defined_config_dict[name] = config_info

def main():
    preload_files     = []
    load_files        = []
    merge_files       = []
    output_file       = None
    arch              = os.getenv("ARCH")
    srcarch           = None
    srctree           = '.'
    kconfig_file      = 'Kconfig'
    cross_compile     = os.getenv("CROSS_COMPILE", "")
    cc                = os.getenv("CC", f"{cross_compile}gcc")
    ld                = os.getenv("LD", f"{cross_compile}ld" )
    verbose           = False
    recommended       = False
    print_options     = DefConfigExplainer.options()
                              
    parser = argparse.ArgumentParser(description="""Defconfig Explainer -- Script to add Kconfig prompts, help, and other explanations to defconfig""")
    parser.add_argument('load_files',
                        nargs   = '*',
                        type    = str,
                        action  = 'store',
                        help    = """Input defconfig files""")
    parser.add_argument('-m', '--merge',
                        type    = str,
                        action  = 'append',
                        help    = """Merge defconfig files""")
    parser.add_argument('-p', '--preload',
                        type    = str,
                        action  = 'append',
                        help    = """Preload defconfig files""")
    parser.add_argument('-k', '--kconfig',
                        type    = str,
                        default = kconfig_file,
                        action  = 'store',
                        help    = f"Kconfig File (default={kconfig_file})"),
    parser.add_argument('-o', '--output',
                        type    = str,
                        default = output_file,
                        action  = 'store',
                        help    = """Output File (default=stdout)"""),
    parser.add_argument('-a', '--arch',
                        default = arch,
                        type    = str,
                        action='store',
                        help    = f"Architecture (default={arch})"),
    parser.add_argument('--srcarch',
                        type    = str,
                        action  = 'store',
                        help    = """Architecture on Source"""),
    parser.add_argument('--srctree',
                        type    = str,
                        default = srctree,
                        action  = 'store',
                        help    = f"Source Tree Path (default={srctree})"),
    parser.add_argument('--cross-compile',
                        type    = str,
                        default = cross_compile,
                        action  = 'store',
                        help    = f"Cross Compiler Prefix (default={cross_compile})"),
    parser.add_argument('--cc',
                        help    = f"C Compiler Command (default={cc})",
                        type    = str,
                        default = cc ,
                        action  = 'store')
    parser.add_argument('--ld',
                        type    = str,
                        default = ld,
                        action  = 'store',
                        help    = f"Linker Command (default={ld})"),
    parser.add_argument('-r', '--recommended',
                        action  = 'store_true',
                        help    = """Recommended Print Option"""),
    parser.add_argument('-O', '--option',
                        default = [],
                        action  = 'append',
                        help    = """OPTION in KEY or kKEY=VALUE)"""),
    parser.add_argument('--option-help',
                        action  = 'store_true',
                        help    = """OPTION help"""),
    parser.add_argument('-v', '--verbose',
                        action  = 'store_true',
                        help    = """Verbose"""),

    args = parser.parse_args()

    load_files        = args.load_files if args.load_files else []
    merge_files       = args.merge      if args.merge      else []
    preload_files     = args.preload    if args.preload    else []
    output_file       = args.output
    kconfig_file      = args.kconfig
    arch              = args.arch
    srctree           = args.srctree
    cross_compile     = args.cross_compile
    cc                = args.cc
    ld                = args.ld
    recommended       = args.recommended
    verbose           = args.verbose

    if args.option_help is True:
        name_title    = "KEY"
        default_title = "DEFAULT"
        help_title    = "DESCRIPTION"
        name_width    = len(name_title)
        default_width = len(default_title)
        help_width    = len(help_title)
        option_list   = []
        for key, info in print_options.items() :
            if   info["value"].__class__ is bool:
                _default = "yes" if info["value"] is True else "no"
            elif info["value"].__class__ is int:
                _default = str(info["value"])
            elif info["value"].__class__ is list:
                _default = "[" + ",".join(info["value"]) + "]"
            else:
                _default = "..."
            _name = info["name"]
            _help = info["help"]
            option_list.append({"name": _name, "default": _default, "help": _help})
            if len(_name) > name_width:
                name_width = len(_name)
            if len(_default) > default_width:
                default_width = len(_default)
            if len(_help) > help_width:
                help_width = len(_help)
        
        _format = "| {:%d} | {:%d} | {:>%d} |" % (name_width, help_width, default_width)
        divider = "|-{}-|-{}-|-{}-|".format("-"*name_width, "-"*help_width, "-"*default_width)
        option_help_list = [_format.format(name_title, help_title, default_title), divider]
        for info in option_list :
            option_help_list.append(_format.format(info["name"], info["help"], info["default"]))
        
        print(f"  -O OPTION, --option OPTION")
        print(f"     OPTION in KEY or KEY=VALUE")
        for help in option_help_list:
            print(f"     {help}")
        sys.exit(0)

    print_format_params = {}
    if recommended is True:
        print_format_params["print_orig_config"]     = True
        print_format_params["print_choice_item"]     = True
     ## print_format_params["print_same_level_item"] = True
        print_format_params["separator_char_list"]   = ['=','-']
        
    for option in args.option :
        if "=" in option:
            key, value = option.split("=",1)
        else:
            key, value = option, "yes"
        name = key.replace("-", "_")
        if name in print_options:
            if print_options[name]["value"].__class__ is list:
                if name in print_format_params:
                    print_format_params[name].append(value)
                else:
                    print_format_params[name] = [value]
            else:
                print_format_params[name] = value
        else:
            raise KeyError(f"{name} is not option name")

    if   args.srcarch is not None:
        srcarch = args.srcarch
    elif arch == 'i386':
        srcarch = 'x86'
    elif arch == 'x86_64':
        srcarch = 'x86'
    elif arch == 'sparc32':
        srcarch = 'sparc'
    elif arch == 'sparc64':
        srcarch = 'sparc'
    elif arch == 'parisc64':
        srcarch = 'parisc'
    else:
        srcarch = arch

    if cross_compile != "":
        if not cc.startswith(cross_compile):
            cc = f"{cross_compile}{cc}"
        if not ld.startswith(cross_compile):
            ld = f"{cross_compile}{ld}"

    if arch is None:
        print("Error: Architecture is not specified.")
        sys.exit(1)

    if verbose is True:
        print(f"## export ARCH={arch}")
        print(f"## export CROSS_COMPILE={cross_compile}")
        print(f"## export CC={cc}")
        print(f"## export LD={ld}")
        print(f"## export SRCARCH={srcarch}")
        print(f"## export srctree={srctree}")
        print(f"## kconfig file = {kconfig_file}")
        print(f"## preload defconfig files = {preload_files}")
        print(f"## load defconfig files    = {load_files}")
        print(f"## merge defconfig files   = {merge_files}")
        print(f"## output file             = {output_file}")
        print(f"## print_format_params     = {print_format_params}")

    os.environ["ARCH"]    = arch
    os.environ["SRCARCH"] = srcarch
    os.environ["CC"]      = cc
    os.environ["LD"]      = ld
    os.environ["srctree"] = srctree

    options = {"undef_warnings": True}

    explainer = DefConfigExplainer(os.path.join(srctree, kconfig_file), options)
    explainer.preload_config_files(defconfig_files=preload_files)
    explainer.load_config_files(defconfig_files=load_files , replace=True )
    explainer.load_config_files(defconfig_files=merge_files, replace=False)
    
    explainer.generate_print_format(print_format_params)

    if output_file is None:
        explainer.print()
    else:
        with open(output_file, "w") as f:
            explainer.print(file=f)

if __name__ == "__main__":
    main()
