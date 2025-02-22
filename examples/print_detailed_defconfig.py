#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause
# Copyright (c) 2025 ikwzm

import sys
import os
import re
import argparse
from kconfiglib import Kconfig, expr_value, \
                       Symbol, Choice, MENU, COMMENT, BOOL, TRISTATE, STRING, INT, HEX, UNKNOWN

class DefConfigPrinter:

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

    def __init__(self, kconfig_file, options={}):
        self.kconf = Kconfig(kconfig_file)

        kconf_options = ['enable_warnings'         , 'disable_warnings'         ,
                         'enable_stderr_warnings'  , 'disable_stderr_warnings'  ,
                         'enable_undef_warnings'   , 'disable_undef_warnings'   ,
                         'enable_override_warnings', 'disable_override_warnings',
                         'enable_redun_warnings'   , 'disable_redun_warnings'  ]
        for name in options:
            if name in kconf_options and hasattr(self.kconf, name):
                getattr(self.kconf, name)()

        self.comment_match = re.compile(r"^#").match
        self.defined_config_list = []
        self.defined_config_dict = {}
        self.max_level           = 0
        self.level_size          = 0
        self.top_node            = None

        self.print_format_params = {
            "print_first_level"     : 1  ,
            "print_max_column"      : 80 ,
            "print_comment"         : False,
            "print_help"            : False,
            "print_orig_config"     : False,
            "print_location"        : False,
            "prompt_indent_char"    : '#',
            "separator_indent_char" : '#',
            "info_indent_char"      : '#',
            "separator_char_list"   : [],
            "separator_format"      : "{separator_indent} {separator_line}",
            "prompt_format"         : "#{separator}\n#{prompt_indent} {prompt}\n#{separator}",
            "help_format"           : "#{info_indent} help\n{help}\n#{info_indent}",
            "help_line_format"      : "#{info_indent}     {help_line}",
            "orig_config_format"    : "#{info_indent} {config}",
            "location_format"       : "#{info_indent} {filename} : {linenr}\n#{info_indent}",
            "menu_end_format"       : "#{prompt_indent} end of {prompt}\n",
        }
        self.generate_print_format()

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
        
    def generate_print_format(self, params={}):
        self.print_format_params.update(params)
        _print_first_level     = self.print_format_params["print_first_level"]
        _print_comment         = self.print_format_params["print_comment"]
        _print_help            = self.print_format_params["print_help"]
        _print_orig_config     = self.print_format_params["print_orig_config"]
        _print_location        = self.print_format_params["print_location"]
        _print_max_column      = self.print_format_params["print_max_column"]
        _prompt_indent_char    = self.print_format_params["prompt_indent_char"]
        _separator_indent_char = self.print_format_params["separator_indent_char"]
        _separator_char_list   = self.print_format_params["separator_char_list"]
        _separator_format      = self.print_format_params["separator_format"]
        _info_indent_char      = self.print_format_params["info_indent_char"]
        _prompt_format         = self.print_format_params["prompt_format"]
        _help_format           = self.print_format_params["help_format"]
        _help_line_format      = self.print_format_params["help_line_format"]
        _orig_config_format    = self.print_format_params["orig_config_format"]
        _location_format       = self.print_format_params["location_format"]
        _menu_end_format       = self.print_format_params["menu_end_format"]

        separator_char_list  = ['']*self.level_size
        separator_char_list[_print_first_level:_print_first_level+len(_separator_char_list)] = _separator_char_list
        self.print_first_level        = _print_first_level
        self.print_comment            = _print_comment
        self.print_help               = _print_help
        self.print_orig_config        = _print_orig_config
        self.print_location           = _print_location
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
            self.print_node_tree(node.list, node.is_choice, file)
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
            curr_node = DefConfigPrinter.Node(menu_node, parent_node, level)
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
    preload_files    = []
    load_files       = []
    merge_files      = []
    output_file      = None
    arch             = os.getenv("ARCH")
    srcarch          = None
    srctree          = '.'
    kconfig_file     = 'Kconfig'
    cross_compile    = os.getenv("CROSS_COMPILE", "")
    cc               = os.getenv("CC", f"{cross_compile}gcc")
    ld               = os.getenv("LD", f"{cross_compile}ld" )
    separator        = False
    with_help        = False
    with_location    = False
    with_orig_config = False
    with_comment     = False
    verbose          = False

    parser = argparse.ArgumentParser(description='Print detailed defconfig')
    parser.add_argument('load_files',
                        nargs   = '*',
                        help    = 'Input defconfig files',
                        type    = str,
                        action  = 'store')
    parser.add_argument('-m', '--merge',
                        help    = 'Merge defconfig files',
                        type    = str,
                        action  = 'append')
    parser.add_argument('-p', '--preload',
                        help    = 'Preload defconfig files',
                        type    = str,
                        action  = 'append')
    parser.add_argument('-k', '--kconfig',
                        help    = f"Kconfig File (default={kconfig_file})",
                        type    = str,
                        default = kconfig_file,
                        action  = 'store')
    parser.add_argument('-o', '--output',
                        help    = "Output File (default=stdout)",
                        type    = str,
                        default = output_file,
                        action  = 'store')
    parser.add_argument('-a', '--arch',
                        help    = f"Architecture (default={arch})",
                        default = arch,
                        type    = str,
                        action='store')
    parser.add_argument('--srcarch',
                        help    = 'Architecture on Source',
                        type    = str,
                        action  = 'store')
    parser.add_argument('--srctree',
                        help    = f"Source Tree Path (default={srctree})",
                        type    = str,
                        default = srctree,
                        action  = 'store')
    parser.add_argument('--cross-compile',
                        help    = f"Cross Compiler Prefix (default={cross_compile})",
                        type    = str,
                        default = cross_compile,
                        action  = 'store')
    parser.add_argument('--cc',
                        help    = f"C Compiler Command (default={cc})",
                        type    = str,
                        default = cc ,
                        action  = 'store')
    parser.add_argument('--ld',
                        help    = f"Linker Command (default={ld})",
                        type    = str,
                        default = ld,
                        action  = 'store')
    parser.add_argument('--separator',
                        help    = 'Print Prompt with Separator',
                        action  = 'store_true')
    parser.add_argument('--with-help',
                        help    = 'Print Prompt with Help',
                        action  = 'store_true')
    parser.add_argument('--with-orig-config',
                        help    = 'Print Prompt with Original Config',
                        action  = 'store_true')
    parser.add_argument('--with-location',
                        help    = 'Print Prompt with Location',
                        action  = 'store_true')
    parser.add_argument('--with-comment',
                        help    = 'Print Prompt with Comment',
                        action  = 'store_true')
    parser.add_argument('-v', '--verbose',
                        help    = 'Verbose',
                        action  = 'store_true')

    args = parser.parse_args()

    load_files       = args.load_files if args.load_files else []
    merge_files      = args.merge      if args.merge      else []
    preload_files    = args.preload    if args.preload    else []
    output_file      = args.output
    kconfig_file     = args.kconfig
    arch             = args.arch
    srctree          = args.srctree
    cross_compile    = args.cross_compile
    cc               = args.cc
    ld               = args.ld
    separator        = args.separator
    with_help        = args.with_help
    with_orig_config = args.with_orig_config
    with_location    = args.with_location
    with_comment     = args.with_comment
    verbose          = args.verbose

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
        print(f"## output file = {output_file}")

    os.environ["ARCH"]    = arch
    os.environ["SRCARCH"] = srcarch
    os.environ["CC"]      = cc
    os.environ["LD"]      = ld
    os.environ["srctree"] = srctree

    options = {"enable_undef_warnings": True}

    printer = DefConfigPrinter(os.path.join(srctree, kconfig_file), options)
    printer.preload_config_files(defconfig_files=preload_files)
    printer.load_config_files(defconfig_files=load_files , replace=True )
    printer.load_config_files(defconfig_files=merge_files, replace=False)
    
    format_params = {}
    if separator is True:
        format_params["separator_char_list"] = ['=', '-']
    if with_help is True:
        format_params["print_help"] = True
    if with_orig_config is True:
        format_params["print_orig_config"] = True
    if with_location is True:
        format_params["print_location"] = True
    if with_comment is True:
        format_params["print_comment"] = True

    printer.generate_print_format(format_params)

    if output_file is None:
        printer.print()
    else:
        with open(output_file, "w") as f:
            printer.print(file=f)

if __name__ == "__main__":
    main()
