from pybroma.PyBroma import Class, Function, FunctionBindField, MemberField, PadField
from pybroma.platforms import Platform
from pybroma.PyBroma import *
from pybroma import BromaTreeVisitor

from pathlib import Path

# From Cython's CodeWriter We will be borrowing this useful code writer to help
# us with writing out our different files we need to make...
from Cython.CodeWriter import LinesResult
from enum import IntEnum
from typing import NamedTuple
import json

# TODO Supply with enums...


class LinesResultPlus(LinesResult):
    def __init__(self):
        super().__init__()
        self.hguard = ""
        self.indents = 0
        self.indentStr = "    "
        self.headerFilename = ""

    def indent(self):
        self.indents += 1

    def dedent(self):
        if self.indents:
            self.indents -= 1

    def setHeaderGuard(self, name: str):
        """Makes a headerGuard for us to start using"""
        self.hguard = name.upper()
        self.putline(f"#ifndef __{self.hguard}_H__")
        self.putline(f"#define __{self.hguard}_H__")
        self.newline()

    def closeHeaderGuard(self):
        self.putline(f"#endif /* __{self.hguard}_H__ */")
        self.hguard = ""

    def comment(self, comment: str):
        """Used to make a single comment for something important"""
        self.startline(f"/* {comment} */")
        self.newline()

    def finalizeAndWriteFile(self, path: Path):
        """Used for dumping the files when we are done writing something down..."""
        if not path.exists():
            path.mkdir()

        # TODO: Warn about User about the dangers overriding previous files inorder to save their
        # own project if something was written in by hand...
        with open(path / self.headerFilename, "w", encoding="utf-8") as w:
            w.write("\n".join(self.lines))

    def include(self, filename: str):
        self.putline(f'#include "{filename}"')

    def predefine_subclass(self, name: str):
        """Predefines a class in a file. This is mainly imeplemnted for intellisense safety..."""
        self.putline(f"class {name};")

    def predefine_many_subclasses(self, superclasses: list[str]):
        superclasses = [s for s in superclasses if not s.startswith("cocos2d::")]
        if superclasses:
            self.newline()
            self.comment("-- Predefined Subclasses --")
            self.newline()
            for s in superclasses:
                self.predefine_subclass(s)
            self.newline()

    def write_delegate(self, mainClass:str , SubClasses:list[str] = []):
        
        if SubClasses:
            self.predefine_many_subclasses(SubClasses)

        self.put(f"class {mainClass}")

        if SubClasses:
            self.put(": " + ", ".join([f"public {s}" for s in SubClasses]))

        self.put(" {")
        self.newline()
        # Used to put as little stress on the user when
        # reverse engineering class objects as possible...
        self.putline("public:")
        self.indent()
    
    def end_delegate(self):
        self.dedent()
        self.putline("};")


    def start_cpp_class(self, mainClass: str, SubClasses: list[str], path=""):
        """assuming every class written here is it's own file this will start the file by introducing the includes.h header..."""
        self.headerFilename = mainClass + ".h"
        self.SrcName = mainClass + ".cpp"
        self.setHeaderGuard(mainClass)
        self.newline()
        self.include("includes.h" if not path else "../includes.h")
        self.newline()

        if SubClasses:
            self.predefine_many_subclasses(SubClasses)

        self.put(f"class {mainClass}")

        if SubClasses:
            self.put(": " + ", ".join([f"public {s}" for s in SubClasses]))

        self.put(" {")
        self.newline()
        # Used to put as little stress on the user when
        # reverse engineering class objects as possible...
        self.putline("public:")
        self.indent()

    def close_cpp_class(self):
        """Closes the C++ class object and then dedents the cursor as well as end the filename..."""
        self.dedent()
        self.putline("};")
        self.newline()
        self.closeHeaderGuard()

    def startline(self, code: str = ""):
        self.put(self.indentStr * self.indents + code)

    def writeline(self, code: str):
        """This is meant to be used and not put() since were trying to indent our functions and class members all within a clean manner"""
        self.putline(self.indentStr * self.indents + code)

    def debug(self):
        print("-- DEBUG --")
        print("\n".join(self.lines))
        print("-- DEBUG END --")

    def external_include(self, header:str):
        self.putline(f"#include <{header}>")


class ClassType(IntEnum):
    """Used to determine the possible path of where a file is going to be written to"""

    Default = 0
    Manager = 1
    Delegate = 2
    CustomCC = 3
    """a CC class without the cocos2d namespace"""
    Cocos2d = 4
    """a libcocos class object"""
    Layer = 5
    Cell = 6
    ToolBox = 7


class SourceFile(NamedTuple):
    srcName: str
    path: str
    cppCls: Class
    type:ClassType

    def translateTypeName(self, tname: str):
        return tname.replace("gd::", "std::")


    def write_function(self, w: LinesResultPlus, f: MemberFunctionProto):
        # start by writing the signature and then write the function if there's no TodoReturn
        signature = self.cppCls.name + "::" + f.name
        # TODO: Optimize this section a little bit more...
        signature += (
            "("
            + ", ".join(
                [
                    (
                        ("struct " + self.translateTypeName(t.name) + " " + a)
                        if t.is_struct
                        else (self.translateTypeName(t.name) + " " + a)
                    )
                    for a, t in f.args.items()
                ]
            )
            + ")"
        )

        if f.ret.name == "TodoReturn":
            # comment out instead
            w.newline()
            w.comment(f"Unknown Return: {signature}" + "{};")
            w.newline()
            return  # exit
        
        w.putline(self.translateTypeName(f.ret.name) + " " + signature)
        # This should be the most appropreate way to deal with this for now...
        
        w.putline("{")
        w.putline("    return;")
        w.putline("}")
        w.newline()
        w.newline()

    def getFunctionsSorted(self):
        return sorted(
            [
                f.getAsFunctionBindField().prototype
                for f in self.cppCls.fields
                if f.getAsFunctionBindField() is not None
            ],
            key=lambda f: f.name,
        
        )

    


    def write_contents(self):
        writer = LinesResultPlus()
        writer.newline()
        writer.include("includes.h")
        writer.newline()
        writer.newline()
        for f in self.getFunctionsSorted():
            self.write_function(writer, f)
        return "\n".join(writer.lines)
    
    def write_delegate(self, writer: LinesResultPlus):
        for proto in self.getFunctionsSorted():
            if proto.is_virtual:
                writer.startline("virtual ")
            elif proto.is_static:
                writer.startline("static ")
            else:
                writer.startline()
            if proto.is_const:
                writer.put("const ")
            writer.put(proto.ret.name + " ")
            writer.put(proto.name)
            writer.put("(")
            if proto.args:
                args = [
                    f"{self.translateTypeName(_type.name)} {name}"
                    for name, _type in proto.args.items()
                ]
                argsline = ", ".join(args)
                writer.put(argsline)
            writer.put(");")
            writer.newline()


    def write(self):
        """Writes the C++ contents"""
        src = Path("src")
        if not src.exists():
            src.mkdir()
        p = src / self.path
        if not p.exists():
            p.mkdir()
        with open(p / self.srcName, "w") as w:
            w.write(self.write_contents())


class ClassHeadersWriter(BromaTreeVisitor):
    """Used for writing Geometry Dash Class Items..."""

    def __init__(self) -> None:
        self.current_writer = None
        self.current_class = ""
        self.includes: list[str] = []
        self.classes: list[SourceFile] = []
        self.delegates: list[Class] = []
        self.pathsdict:dict[str , list[str]] = {}

        super().__init__()

    def determinePath(self, node: Class):
        """determines if the class object we're about to use is a delegate,
        a robtop CC class (Custom Libcocos class) or a CellType..."""
        name = node.name
        if name.startswith("cocos2d::") or name.startswith("DS_Dictionary"):
            # This one is an ignore flag we will be installing cocos-headers to make up for that...
            return ClassType.Cocos2d
        elif "delegate" in name.lower():
            # Make an effort to Hold onto all delegates for later use...
            self.delegates.append(node)
            return ClassType.Delegate
        elif name.startswith("CC"):
            return ClassType.CustomCC
        elif name.startswith(("TableView", "BoomListView")) or name.lower().endswith(
            "cell"
        ):
            return ClassType.Cell
        elif name.lower().endswith("manager"):
            return ClassType.Manager
        elif name.lower().endswith("layer"):
            return ClassType.Layer
        # A ToolBox is simillar to a delegate but it's treated more as special namespace...
        elif name == "LevelTools" or name.lower().endswith("toolbox"):
            return ClassType.ToolBox
        else:
            return ClassType.Default

    def typeForDirectory(self, t: ClassType):
        # -- Ignore cocos2d things and delegates! --
        base = Path("headers")

        if t == ClassType.Cocos2d or t == ClassType.Delegate:
            return None

        elif t == ClassType.Manager:
            path = "Managers"

        elif t == ClassType.Cell:
            path = "Cells"

        elif t == ClassType.ToolBox:
            path = "Tools"

        elif t == ClassType.CustomCC:
            path = "CustomCCClasses"

        elif t == ClassType.Layer:
            path = "Layers"

        # Put defaults into the common directory as opposed
        # to the place where includes.h will be located for
        # tidiness...
        else:
            path = "Common"

        if not self.pathsdict.get(path):
            self.pathsdict[path] = []

        return base / path

    def visit_PadField(self, node: PadField):
        self.current_writer.comment("PAD")
        self.current_writer.newline()
        return super().visit_PadField(node)

    def visit_MemberField(self, node: MemberField):
        self.current_writer.startline(self.fixTypename(node.type.name))
        self.current_writer.put(" ")
        self.current_writer.put(node.name + ";")
        self.current_writer.newline()
        return super().visit_MemberField(node)

    def visit_Class(self, node: Class):
        self.current_class = node
        # visit the class in question or else otherwise simply ignore it...
        t = self.determinePath(node)
        if path := self.typeForDirectory(t):
            self.current_writer = LinesResultPlus()
            self.current_writer.start_cpp_class(node.name, node.superclasses, str(path))
            # write down our the code for it to function
            super().visit_Class(node)
            self.current_writer.close_cpp_class()

            # close the writer out
            # self.current_writer.debug()
            self.current_writer.finalizeAndWriteFile(path)
            destination = path.parts[-1]
            self.includes.append(destination + "/" + self.current_writer.headerFilename)
            self.pathsdict[destination].append(destination + "/" + self.current_writer.headerFilename)
            self.classes.append(SourceFile(self.current_writer.SrcName, destination, node, t))
            self.current_writer = None

    def fixTypename(self, type: str):
        return type.replace("gd::", "std::")

    def visit_FunctionBindField(self, node: FunctionBindField):
        # TODO: Maybe add Docs?...
        proto = node.prototype
        if proto.is_virtual:
            self.current_writer.startline("virtual ")
        elif proto.is_static:
            self.current_writer.startline("static ")
        else:
            self.current_writer.startline()
        if proto.is_const:
            self.current_writer.put("const ")
        self.current_writer.put(proto.ret.name + " ")
        self.current_writer.put(proto.name)
        self.current_writer.put("(")
        if proto.args:
            args = [
                f"{self.fixTypename(_type.name)} {name}"
                for name, _type in proto.args.items()
            ]
            argsline = ", ".join(args)
            self.current_writer.put(argsline)
        self.current_writer.put(");")
        self.current_writer.newline()

    def write_sources(self):
        for files in self.classes:
            files.write()

    def write_includes(self):
        writer = LinesResultPlus()
        writer.putline("#ifndef __INCLUDES_H__")
        writer.putline("#define __INCLUDES_H__")
        writer.newline()
        writer.newline()
        writer.comment("External Resources")
        writer.putline("#ifdef _WIN32")
        writer.putline("    #define WIN32_LEAN_AND_MEAN")
        writer.putline("    #include <windows.h>")
        writer.putline("#endif /* _WIN32 */")
        writer.external_include("cocos2d.h")
        writer.external_include("fmt/format.h")
        writer.external_include("fmod/fmod.h")
        writer.external_include("cstdlib")
        writer.external_include("cstring")
        writer.external_include("string")
        writer.external_include("map")
        writer.external_include("unordered_map")
        writer.newline()

        writer.comment("Macros")
        writer.putline("#ifndef TodoReturn")
        writer.putline("    #define TodoReturn void*")
        writer.putline("#endif /* TodoReturn */")
        # Includes 

        for path, names in sorted(list(self.pathsdict.items()), key=lambda x: x[0]):
            writer.comment(path)
            writer.newline()
            for n in names:
                writer.include(n)
            writer.newline()
            writer.newline()

        # TODO: Seperate Delegates into another file in a future version of this tool

        # Delegates
        writer.comment("Delegates")
        for d in self.delegates:
            writer.write_delegate(d.name, d.superclasses)
            SourceFile("", "", d, ClassType.Delegate).write_delegate(writer)
            writer.end_delegate()
            writer.newline()
            writer.newline()

        writer.comment("TODO: Enums")
        writer.newline()
        writer.newline()


        writer.putline("#endif /* __INCLUDES_H__ */")

        # The cherry on top is this...
        with open("headers/includes.h", "w") as w:
            w.write("\n".join(writer.lines))
    
    @staticmethod
    def write_vscode_header():
        """This feature is windows only but as an extra blessing to the user I will setup the configurations for intellisense for you"""
        _json = {
            "configurations": [
                {
                    "name": "Win32",
                    "includePath": [
                        "${workspaceFolder}/**",
                        "${workspaceFolder}/cocos2d/**",
                    ],
                    "defines": [
                        "_DEBUG",
                        "UNICODE",
                        "_UNICODE"
                    ],
                    "windowsSdkVersion": "10.0.19041.0",
                    "compilerPath": "cl.exe",
                    "cStandard": "c17",
                    "cppStandard": "c++17",
                    "intelliSenseMode": "windows-msvc-x64"
                }
            ],
            "version": 4
        }

        vscode = Path(".vscode")
        if not vscode.exists():
            vscode.mkdir()
        
        with open(vscode / "c_cpp_properties.json", "w") as w:
            json.dump(_json, w)


def write_everything():
    _dir = Path(".temp")
    with open(_dir / "Cocos2d.bro", "r") as fp:
        code = fp.read() + "\n"
    with open(_dir / "GeometryDash.bro", "r") as fp:
        code += fp.read() + "\n"
    with open(_dir / "Extras.bro", "r") as fp:
        code += fp.read() + "\n" 
    with open("_temp.bro", "w") as w:
        w.write(code)

    chw = ClassHeadersWriter()
    chw.start(Root("_temp.bro"))
    chw.write_sources()
    chw.write_includes()


