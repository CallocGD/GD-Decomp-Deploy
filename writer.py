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
    
    def write_memberField(self, name:str, type:str):
        self.current_writer.startline(self.fixTypename(type))
        self.current_writer.put(" ")
        self.current_writer.put(name + ";")
        self.current_writer.newline()

    def visit_MemberField(self, node: MemberField):
        

        # NOTE: We need to split up geode's RSVs since were doing A Decomp of What Robtop Has (Not Geode)
        if node.type.name.startswith("geode::SeedValue"):
            # Split into 3 member fields insead of One...
            name = node.name
            typename = node.type.name.rstrip("geode::SeedValue")
            for letter in list(typename):
                if letter == "R":
                    self.write_memberField(name + "Rand", "int")
                elif letter == "S":
                    self.write_memberField(name + "Seed", "int")
                elif letter == "V":
                    self.write_memberField(name, "int")
            
        else:
            self.write_memberField(node.name, node.type.name)
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
         
            if not "pugi::" in self.current_writer.headerFilename:
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
        writer.putline("""

#ifndef PASS
    /* Function will not be decompiled yet due to **Certain Defined Restraints** Specified by `Reason` */
    #define PASS(Func, Reason) Func{return;};
#endif

#ifndef NOOP
    /* Function has No Operations Involved */
    #define NOOP(Func) Func{};
#endif


""")

        writer.putline("""

/* I Blame Geode for adding this namespace -_-
adding this in to prevent intellisense from complaining 
to me more , please try not to send me pull requests
with the gd namespace it's here only if I'm lazily merging class members in.

If you send me pull requests with the namespace of gd anywhere in the src folder, I will disown you 
- Calloc
*/

namespace gd = std;

""")

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



        writer.putline(

"""

/* ENUMS */

/* Enums are from https://github.com/geode-sdk/bindings/blob/main/bindings/include/Geode/Enums.hpp 
 *
 * We will use these unless the assembly doesn't match because I got tired of saying kEnumType everytime.
 * Not sure on how we will verify functions as 1 to 1 matching assembly yet... - Calloc 
 */

// thanks pie
enum class SearchType {
    Search = 0,
    Downloaded = 1,
    MostLiked = 2,
    Trending = 3,
    Recent = 4,
    UsersLevels = 5,
    Featured = 6,
    Magic = 7,
    Sends = 8,
    MapPack = 9,
    MapPackOnClick = 10,
    Awarded = 11,
    Followed = 12,
    Friends = 13,
    Users = 14,
    LikedGDW = 15,
    HallOfFame = 16,
    FeaturedGDW = 17,
    Similar = 18,
    Type19 = 19,
    TopListsUnused = 20,
    DailySafe = 21,
    WeeklySafe = 22,
    EventSafe = 23,
    Reported = 24,
    LevelListsOnClick = 25,
    Type26 = 26,
    Sent = 27,
    MyLevels = 98,
    SavedLevels = 99,
    FavouriteLevels = 100,
    SmartTemplates = 101,
    MyLists = 102,
    FavouriteLists = 103
};

enum class GameObjectType {
    Solid = 0,
    Hazard = 2,
    InverseGravityPortal = 3,
    NormalGravityPortal = 4,
    ShipPortal = 5,
    CubePortal = 6,
    Decoration = 7,
    YellowJumpPad = 8,
    PinkJumpPad = 9,
    GravityPad = 10,
    YellowJumpRing = 11,
    PinkJumpRing = 12,
    GravityRing = 13,
    InverseMirrorPortal = 14,
    NormalMirrorPortal = 15,
    BallPortal = 16,
    RegularSizePortal = 17,
    MiniSizePortal = 18,
    UfoPortal = 19,
    Modifier = 20,
    Breakable = 21,
    SecretCoin = 22,
    DualPortal = 23,
    SoloPortal = 24,
    Slope = 25,
    WavePortal = 26,
    RobotPortal = 27,
    TeleportPortal = 28,
    GreenRing = 29,
    Collectible = 30,
    UserCoin = 31,
    DropRing = 32,
    SpiderPortal = 33,
    RedJumpPad = 34,
    RedJumpRing = 35,
    CustomRing = 36,
    DashRing = 37,
    GravityDashRing = 38,
    CollisionObject = 39,
    Special = 40,
    SwingPortal = 41,
    GravityTogglePortal = 42,
    SpiderOrb = 43,
    SpiderPad = 44,
    TeleportOrb = 46,
    AnimatedHazard = 47,
};

enum class GJGameEvent {
    None = 0,
    TinyLanding = 1,
    FeatherLanding = 2,
    SoftLanding = 3,
    NormalLanding = 4,
    HardLanding = 5,
    HitHead = 6,
    OrbTouched = 7,
    OrbActivated = 8,
    PadActivated = 9,
    GravityInverted = 10,
    GravityRestored = 11,
    NormalJump = 12,
    RobotBoostStart = 13,
    RobotBoostStop = 14,
    UFOJump = 15,
    ShipBoostStart = 16,
    ShipBoostEnd = 17,
    SpiderTeleport = 18,
    BallSwitch = 19,
    SwingSwitch = 20,
    WavePush = 21,
    WaveRelease = 22,
    DashStart = 23,
    DashStop = 24,
    Teleported = 25,
    PortalNormal = 26,
    PortalShip = 27,
    PortalBall = 28,
    PortalUFO = 29,
    PortalWave = 30,
    PortalRobot = 31,
    PortalSpider = 32,
    PortalSwing = 33,
    YellowOrb = 34,
    PinkOrb = 35,
    RedOrb = 36,
    GravityOrb = 37,
    GreenOrb = 38,
    DropOrb = 39,
    CustomOrb = 40,
    DashOrb = 41,
    GravityDashOrb = 42,
    SpiderOrb = 43,
    TeleportOrb = 44,
    YellowPad = 45,
    PinkPad = 46,
    RedPad = 47,
    GravityPad = 48,
    SpiderPad = 49,
    PortalGravityFlip = 50,
    PortalGravityNormal = 51,
    PortalGravityInvert = 52,
    PortalFlip = 53,
    PortalUnFlip = 54,
    PortalNormalScale = 55,
    PortalMiniScale = 56,
    PortalDualOn = 57,
    PortalDualOff = 58,
    PortalTeleport = 59,
    Checkpoint = 60,
    DestroyBlock = 61,
    UserCoin = 62,
    PickupItem = 63,
    CheckpointRespawn = 64,
    FallLow = 65,
    FallMed = 66,
    FallHigh = 67,
    FallVHigh = 68,
    JumpPush = 69,
    JumpRelease = 70,
    LeftPush = 71,
    LeftRelease = 72,
    RightPush = 73,
    RightRelease = 74,
    PlayerReversed = 75,
    FallSpeedLow = 76,
    FallSpeedMed = 77,
    FallSpeedHigh = 78
};

enum class PulseEffectType {
};
enum class TouchTriggerType {
};
enum class PlayerButton {
    Jump = 1,
    Left = 2,
    Right = 3,
};
enum class GhostType {
};
enum class TableViewCellEditingStyle {
};
enum class UserListType {
    Friends = 0,
    Blocked = 1,
};
enum class GJErrorCode {
    NotFound = -1,
    UpdateApp = 3
};
enum class AccountError {
    EmailsDoNotMatch = -99,
    AlreadyLinkedToDifferentSteamAccount = -13,
    AccountDisabled = -12,
    AlreadyLinkedToDifferentAccount = -10,
    TooShortLessThan3 = -9,
    TooShortLessThan6 = -8,
    PasswordsDoNotMatch = -7,
    InvalidEmail = -6,
    InvalidPassword = -5,
    InvalidUsername = -4,
    AlreadyUsedEmail = -3,
    AlreadyUsedUsername = -2
};
enum class GJSongError {
    DownloadSongFailed = 1,
    DownloadSFXFailed = 2
};
enum class GJSongType {}; //probs normal and ncs
enum class LikeItemType {
    Unknown = 0,
    Level = 1,
    Comment = 2,
    AccountComment = 3,
    LevelList = 4
};

enum class CommentError {
};
enum class BackupAccountError {
    BackupOrSyncFailed = -3,
    LoginFailed = -2
};
enum class GJMusicAction {
    DownloadOrUpdate = 2,
    UpdateSFXLibrary = 4,
    UpdateMusicLibrary = 6
};
enum class CellAction {};
enum class GJActionCommand {};
enum class DifficultyIconType {
    ShortText = 0,
    DefaultText = 1,
    NoText = 2
};
enum class GauntletType {
    Fire = 0,
    Ice = 2,
    Poison = 3,
    Shadow = 4,
    Lava = 5,
    Bonus = 6,
    Chaos = 7,
    Demon = 8,
    Time = 9,
    Crystal = 0xA,
    Magic = 0xB,
    Spike = 0xC,
    Monster = 0xD,
    Doom = 0xE,
    Death = 0xF,
    Forest = 0x10,
    Rune = 0x11,
    Force = 0x12,
    Spooky = 0x13,
    Dragon = 0x14,
    Water = 0x15,
    Haunted = 0x16,
    Acid = 0x17,
    Witch = 0x18,
    Power = 0x19,
    Potion = 0x1A,
    Snake = 0x1B,
    Toxic = 0x1C,
    Halloween = 0x1D,
    Treasure = 0x1E,
    Ghost = 0x1F,
    Spider = 0x20,
    Gem = 0x21,
    Inferno = 0x22,
    Portal = 0x23,
    Strange = 0x24,
    Fantasy = 0x25,
    Christmas = 0x26,
    Surprise = 0x27,
    Mystery = 0x28,
    Cursed = 0x29,
    Cyborg = 0x2A,
    Castle = 0x2B,
    Grave = 0x2C,
    Temple = 0x2D,
    World = 0x2E,
    Galaxy = 0x2F,
    Universe = 0x30,
    Discord = 0x31,
    Split = 0x32
};
enum class GJMPErrorCode {};
enum class GJTimedLevelType {
    Daily = 0,
    Weekly = 1,
    Event = 2
};
enum class SongSelectType {
    Default = 0,
    Custom = 1
};
enum class AudioTargetType {};
enum class FMODReverbPreset {
    Generic = 0,
    PaddedCell = 1,
    Room = 2,
    Bathroom = 3,
    Livingroom = 4,
    Stoneroom = 5,
    Auditorium = 6,
    ConvertHall = 7,
    Cave = 8,
    Arena = 9,
    Hangar = 0xA,
    CarpettedHallway = 0xB,
    Hallway = 0xC,
    StoneCorridor = 0xD,
    Alley = 0xE,
    Forest = 0xF,
    City = 0x10,
    Mountains = 0x11,
    Quarry = 0x12,
    Plain = 0x13,
    ParkingLot = 0x14,
    SewerPipe = 0x15,
    Underwater = 0x16
};
enum class DemonDifficultyType {
    HardDemon = 0,
    EasyDemon = 3,
    MediumDemon = 4,
    InsaneDemon = 5,
    ExtremeDemon = 6
};
enum class PlayerCollisionDirection {
    Top = 0,
    Bottom = 1,
    Left = 2,
    Right = 3
};
enum class ChestSpriteState {};
enum class FormatterType {};
enum class AudioModType {};
enum class GJAreaActionType {};
enum class GJSmartDirection {};
enum class SmartBlockType {};
enum class TouchTriggerControl {};
enum class SmartPrefabResult {};
enum class AudioSortType {};
enum class spriteMode {};
enum class GJAssetType {};
enum class CommentKeyType {
    Level = 0,
    User = 1,
    LevelList = 2
};
enum class LevelLeaderboardMode {
    Time = 0,
    Points = 1
};
enum class StatKey {};
enum class TextStyleType {
    Default = 0,
    Colored = 1,
    Instant = 2,
    Shake = 3,
    Delayed = 4
};

enum class InputValueType {};
enum class GJInputStyle {};
enum class GJDifficultyName {
    Short = 0,
    Long = 1
};
enum class GJFeatureState {
    None = 0,
    Featured = 1,
    Epic = 2,
    Legendary = 3,
    Mythic = 4
};
enum class GJKeyGroup {};
enum class GJKeyCommand {};
enum class SelectSettingType {};
enum class gjParticleValue {
    MaxParticles = 1,
    Duration = 2,
    Lifetime = 3,
    PlusMinus1 = 4,
    Emission = 5,
    Angle = 6,
    PlusMinus2 = 7,
    Speed = 8,
    PlusMinus3 = 9,
    PosVarX = 0xA,
    PosVarY = 0xB,
    GravityX = 0xC,
    GravityY = 0xD,
    AccelRad = 0xE,
    PlusMinus4 = 0xF,
    AccelTan = 0x10,
    PlusMinus5 = 0x11,
    StartSize = 0x12,
    PlusMinus6 = 0x13,
    EndSize = 0x14,
    PlusMinus7 = 0x15,
    StartSpin = 0x16,
    PlusMinus8 = 0x17,
    EndSpin = 0x18,
    PlusMinus9 = 0x19,
    StartR = 0x1A,
    PlusMinus10 = 0x1B,
    StartG = 0x1C,
    PlusMinus11 = 0x1D,
    StartB = 0x1E,
    PlusMinus12 = 0x1F,
    StartA = 0x20,
    PlusMinus13 = 0x21,
    EndR = 0x22,
    PlusMinus14 = 0x23,
    EndG = 0x24,
    PlusMinus15 = 0x25,
    EndB = 0x26,
    PlusMinus16 = 0x27,
    EndA = 0x28,
    PlusMinus17 = 0x29,
    FadeIn = 0x2A,
    PlusMinus18 = 0x2B,
    FadeOut = 0x2C,
    PlusMinus19 = 0x2D,
    FrictionP = 0x2E,
    PlusMinus20 = 0x2F,
    Respawn = 0x30,
    PlusMinus21 = 0x31,
    StartRad = 0x32,
    PlusMinus22 = 0x33,
    EndRad = 0x34,
    PlusMinus23 = 0x35,
    RotSec = 0x36,
    PlusMinus24 = 0x37,
    FrictionS = 0x45,
    PlusMinus25 = 0x46,
    FrictionR = 0x47,
    PlusMinus26 = 0x48
};
enum class ColorSelectType {};
enum class AudioGuidelinesType {
    GuidelineCreator = 0,
    BPMFinder = 1
};
enum class SmartBrowseFilter {};
enum class GJUITouchEvent {};
enum class ObjectScaleType {
    XY = 0,
    X = 1,
    Y = 2
};
enum class SavedActiveObjectState {};
enum class SavedSpecialObjectState {};
enum class SavedObjectStateRef {};


enum class CommentType {
    Level = 0,
    Account = 1,
    FriendRequest = 2,
    ListDescription = 4,
};

enum class BoomListType {
    Default = 0x0,
    User = 0x2,
    Stats = 0x3,
    Achievement = 0x4,
    Level = 0x5,
    Level2 = 0x6,
    Comment = 0x7,
    Comment2 = 0x8,
    Comment3 = 0x9,
    Song = 0xc,
    Score = 0xd,
    MapPack = 0xe,
    CustomSong = 0xf,
    Comment4 = 0x10,
    User2 = 0x11,
    Request = 0x12,
    Message = 0x13,
    LevelScore = 0x14,
    Artist = 0x15,
    SmartTemplate = 0x16,
    SFX = 0x17,
    SFX2 = 0x18,
    CustomMusic = 0x19,
    Options = 0x1a,
    LevelList = 0x1b,
    Level3 = 0x1c,
    LevelList2 = 0x1d,
    LevelList3 = 0x1e,
    Level4 = 0x1f,
    LocalLevelScore = 0x21,
    URL = 0x22,
};

enum class CurrencySpriteType {
    Orb = 1,
    Star = 2,
    Diamond = 3,
    FireShard = 4,
    IceShard = 5,
    PoisonShard = 6,
    ShadowShard = 7,
    LavaShard = 8,
    DemonKey = 9,
    EarthShard = 10,
    BloodShard = 11,
    MetalShard = 12,
    LightShard = 13,
    SoulShard = 14,
    Moon = 15
};

enum class CurrencyRewardType {
    // todo
};

enum class MenuAnimationType {
    Scale = 0,
    Move = 1,
};

enum class ShopType {
    Normal,
    Secret,
    Community
};

// Geode Addition
enum class ZLayer {
    B5 = -5,
    B4 = -3,
    B3 = -1,
    B2 = 1,
    B1 = 3,
    Default = 0,
    T1 = 5,
    T2 = 7,
    T3 = 9,
    T4 = 11,
};

enum class UpdateResponse {
    Unknown,
    UpToDate,
    GameVerOutOfDate,
    UpdateSuccess,
};



enum class UnlockType {
    Cube = 0x1,
    Col1 = 0x2,
    Col2 = 0x3,
    Ship = 0x4,
    Ball = 0x5,
    Bird = 0x6,
    Dart = 0x7,
    Robot = 0x8,
    Spider = 0x9,
    Streak = 0xA,
    Death = 0xB,
    GJItem = 0xC,
    Swing = 0xD,
    Jetpack = 0xE,
    ShipFire = 0xF
};

enum class SpecialRewardItem {
    None = 0x0,
    FireShard = 0x1,
    IceShard = 0x2,
    PoisonShard = 0x3,
    ShadowShard = 0x4,
    LavaShard = 0x5,
    BonusKey = 0x6,
    Orbs = 0x7,
    Diamonds = 0x8,
    CustomItem = 0x9,
    EarthShard = 0xA,
    BloodShard = 0xB,
    MetalShard = 0xC,
    LightShard = 0xD,
    SoulShard = 0xE
};

enum class EditCommand {
    SmallLeft = 1,
    SmallRight = 2,
    SmallUp = 3,
    SmallDown = 4,

    Left = 5,
    Right = 6,
    Up = 7,
    Down = 8,

    BigLeft = 9,
    BigRight = 10,
    BigUp = 11,
    BigDown = 12,

    TinyLeft = 13,
    TinyRight = 14,
    TinyUp = 15,
    TinyDown = 16,

    HalfLeft = 17,
    HalfRight = 18,
    HalfUp = 19,
    HalfDown = 20,

    FlipX = 21,
    FlipY = 22,
    RotateCW = 23,
    RotateCCW = 24,
    RotateCW45 = 25,
    RotateCCW45 = 26,
    RotateFree = 27,
    RotateSnap = 28,

    Scale = 29,
    ScaleXY = 30,
    Skew = 31
};

// Geode Addition
enum class PlaybackMode {
    Not = 0,
    Playing = 1,
    Paused = 2,
};

enum class SelectArtType {
    Background = 0,
    Ground = 1,
};

enum class UndoCommand {
    Delete = 1,
    New = 2,
    Paste = 3,
    DeleteMulti = 4,
    Transform = 5,
    Select = 6,
};

enum class EasingType {
    None = 0,
    EaseInOut = 1,
    EaseIn = 2,
    EaseOut = 3,
    ElasticInOut = 4,
    ElasticIn = 5,
    ElasticOut = 6,
    BounceInOut = 7,
    BounceIn = 8,
    BounceOut = 9,
    ExponentialInOut = 10,
    ExponentialIn = 11,
    ExponentialOut = 12,
    SineInOut = 13,
    SineIn = 14,
    SineOut = 15,
    BackInOut = 16,
    BackIn = 17,
    BackOut = 18,
};

enum class GJDifficulty {
    Auto = 0,
    Easy = 1,
    Normal = 2,
    Hard = 3,
    Harder = 4,
    Insane = 5,
    Demon = 6,
    DemonEasy = 7,
    DemonMedium = 8,
    DemonInsane = 9,
    DemonExtreme = 10
};

enum class GJLevelType {
    Local = 1,
    Editor = 2,
    Saved = 3
};

enum class GJRewardType
{
    Unknown = 0x0,
    Small = 0x1,
    Large = 0x2,
    SmallTreasure = 0x3,
    LargeTreasure = 0x4,
    Key10Treasure = 0x5,
    Key25Treasure = 0x6,
    Key50Treasure = 0x7,
    Key100Treasure = 0x8
};

enum class IconType {
    Cube = 0,
    Ship = 1,
    Ball = 2,
    Ufo = 3,
    Wave = 4,
    Robot = 5,
    Spider = 6,
    Swing = 7,
    Jetpack = 8,
    DeathEffect = 98,
    Special = 99,
    Item = 100,
    ShipFire = 101,
};

enum class GJChallengeType {
    Unknown = 0,
    Orbs = 1,
    UserCoins = 2,
    Stars = 3,
    Moons = 4,
};

enum class GJScoreType {
    Unknown = 0,
    Creator = 1
};

enum class LevelLeaderboardType {
    Friends = 0,
    Global = 1,
    Weekly = 2
};

// Thanks Calloc -_- Yeah I got no credit for this one...
enum class GJHttpType {
    UploadLevel = 0x1,
    GetOnlineLevels = 0x2,
    GetMapPacks = 0x3,
    DownloadLevel = 0x4,
    UpdateLevel = 0x5,
    RateStars = 0x6,
    DeleteServerLevel = 0x7,
    SetLevelStars = 0x8,
    SetLevelFeatured = 0x9,
    UpdateUserScore = 0xA,
    GetLeaderboardScores = 0xB,
    GetLevelComments = 0xC,
    UploadComment = 0xD,
    DeleteComment = 0xE,
    LikeItem = 0xF,
    RestoreItems = 0x10,
    SubmitUserInfo = 0x11,
    ReportLevel = 0x12,
    GetSongInfo = 0x13,
    BackupAccount = 0x14,
    SyncAccount = 0x15,
    RegisterAccount = 0x16,
    LoginAccount = 0x17,
    UpdateDescription = 0x18,
    GetAccountComments = 0x19,
    UpdateAccountSettings = 0x1A,
    GetGJUserInfo = 0x1B,
    GetFriendRequests = 0x1C,
    UploadFriendRequest = 0x1D,
    DeleteFriendRequest = 0x1E,
    AcceptFriendRequest = 0x1F,
    ReadFriendRequest = 0x20,
    RemoveFriend = 0x21,
    BlockUser = 0x22,
    UnblockUser = 0x23,
    GetUserList = 0x24,
    GetUserMessages = 0x25,
    DownloadUserMessage = 0x26,
    DeleteUserMessages = 0x27,
    UploadUserMessage = 0x28,
    GetUsers = 0x29,
    BanUser = 0x2A,
    RequestUserAccess = 0x2B,
    GetLevelSaveData = 0x2C,
    SuggestLevelStars = 0x2D,
    GetGJRewards = 0x2E,
    GetGJChallenges = 0x2F,
    GetGJDailyLevelState = 0x30,
    Unknown49 = 0x31,
    RateDemon = 0x32,
    GetLevelLeaderboard = 0x33,
    GetGauntlets = 0x34,
    GetTopArtists = 0x35,
    GetAccountBackupURL = 0x36,
    GetAccountSyncURL = 0x37,

    // Yet to be added by Robtop in 2.21
    // joinLobby = 0x39,
    // ExitMPLobby = 0x3a,
    GetLevelLists = 0x3c,
    DeleteServerLevelList = 0x3e,
};

enum class DialogChatPlacement {
    Center = 0,
    Top = 1,
    Bottom = 2,
};

enum class DialogAnimationType {
    Instant = 0,
    FromCenter = 1,
    FromLeft = 2,
    FromRight = 3,
    FromTop = 4,
    // a 5th type is defined which acts exactly the same as FromTop
    FromBottom = 5 
};

// Geode Addition
enum class ComparisonType {
    Equals = 0,
    Larger = 1,
    Smaller = 2,
};

// Geode Addition
enum class MoveTargetType {
    Both = 0,
    XOnly = 1,
    YOnly = 2,
};

// Geode Addition
enum class TouchToggleMode {
    Normal = 0,
    ToggleOn = 1,
    ToggleOff = 2,
};

// Geode Addition
enum class LeaderboardState {
    Default = 0,
    Top100 = 1,
    Global = 2,
    Creator = 3,
    Friends = 4,
};

// Wylie Addition (https://github.com/Wyliemaster/GD-Decompiled/blob/main/GD/code/headers/Layers/LevelSettingsLayer.h)
enum class Speed {
	Normal = 0,
	Slow = 1,
	Fast = 2,
	Faster = 3,
	Fastest = 4,
};

"""



        )



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
    code = open(_dir / "Cocos2d.bro", "rb").read() + b"\n"
    code += open(_dir / "GeometryDash.bro", "rb").read() + b"\n"
    code += open(_dir / "Extras.bro", "rb").read() + b"\n" 
    
    with open("_temp.bro", "wb") as w:
        w.write(code)

    _headers = Path("headers")
    if not _headers.exists():
        _headers.mkdir()
    

    chw = ClassHeadersWriter()
    chw.start(Root("_temp.bro"))
    chw.write_sources()
    chw.write_includes()



    chw.write_sources()
    chw.write_includes()


