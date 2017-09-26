"""
Expand all the posibilities based on the branching preprocessor directives
found in the code (#if, #ifdef, #ifndef).

TODO:

Funcionality:
    - Annidated branches
    - elif
    - Expand macros

Optimizations:
    - Port to C++ and use CLANG-tooling instead of calling gcc -E
    - Process only once branches with the same symbol/condition
    - Process only once branches with the same content
    - Don't calculate both paths for branches with #define or #undef in the code
    - Don't calculate the "false" branch for branches without #else (just return empty)
"""


import os
import re
import sys
import tempfile
import uuid
from copy import copy
from subprocess import call

BRANCHING_START = ("#if", "#ifdef", "#ifndef")
BRANCHING = BRANCHING_START + ("#elseif", "#else", "#endif")
BRANCHING_MARK = "__mark__:"
BRANCH_START_REGEX = re.compile(r"#.*[if|ifdef|if|elif|ifndef]\s+(\w+)")
CONDITION_START_REGEX = re.compile(r"#.*[if|ifdef|if|elif|ifndef]\s+")
FAKE_CONDITION = "____FAKECONDITION____"


class Tree():
    def __init__(self):
        self.left = None
        self.right = None
        self.code = None
        self.branchtext = None
        self.is_left = None
        self.path = []


def disable_other_directives(text):
    lines = text.splitlines()
    newlines = []

    for idx, line in enumerate(lines):
        sline = line.strip()

        if sline.strip().startswith("#"):
            # preprocessor #directive
            tokens = sline.split(" ")
            firsttok = tokens[0]

            if firsttok not in BRANCHING:
                newtok = "__#__" + firsttok[1:]
                newline = " ".join([newtok] + tokens[1:])
            else:
                newline = sline
                # # branching directive, add a comment with:
                # # // lineno:hash
                # newline = ' '.join(tokens)
                if firsttok in BRANCHING_START:
                    newline += " // " + BRANCHING_MARK + "{}:{}".format(idx, uuid.uuid4())
            newlines.append(newline)
        else:
            newlines.append(line)

    return "\n".join(newlines)


def mark_endif(textlines, mark):
    newlines = []
    for idx, line in enumerate(textlines):
        sline = line.strip()

        if sline.startswith("#endif"):
            # add the mark of the opening branch and finish
            newlines.append(sline)
            newlines.append(mark)
            newlines.extend(textlines[idx + 1:])
            break
        else:
            newlines.append(line)

    return newlines


def replace_branch_condition(line):
    match = CONDITION_START_REGEX.match(line)
    # match = BRANCH_START_REGEX.match(line)
    if not match:
        raise Exception("Condition not found for branch: ", line)
    return line[:match.end()] + FAKE_CONDITION


def find_endpos(lines, mark):
    for idx, line in enumerate(lines):
        if mark in line:
            return idx

    raise Exception("Mark not found: " + mark)


# FIXME: shitty resource handling
def get_branches(textlines):
    handle, inname = tempfile.mkstemp(suffix=".c")
    open(inname, "w").write("\n".join(textlines))
    os.close(handle)

    # Symbol-defined branch
    handle, outf = tempfile.mkstemp()
    with open(outf) as out1:
        name = out1.name
        cmd = ["gcc", "-E", "-D%s" % FAKE_CONDITION, "-o%s" % name, inname]
        call(cmd)
        text1 = list(
                    filter(
                        lambda x: not x.startswith("# 1"),
                        open(name).read().splitlines()
                    )
                )
    os.close(handle)

    handle, outf = tempfile.mkstemp()
    with open(outf) as out2:
        name = out2.name
        cmd = ["gcc", "-E", "-U%s" % FAKE_CONDITION, "-o%s" % name, inname]
        call(cmd)
        text2 = list(
                    filter(
                        lambda x: not x.startswith("# 1"),
                        open(name).read().splitlines()
                    )
                )
    os.close(handle)

    return text1, text2


EXPAND_COUNT = 0


def expand_branch(text):
    global EXPAND_COUNT
    # FIXME: this doesnt handle inner branches
    changed = False
    branchtext = None
    textlines = text.splitlines()

    for idx, line in enumerate(textlines):
        sline = line.strip()

        if BRANCH_START_REGEX.match(line):
            EXPAND_COUNT += 1
            # we eliminated the other directives, so this is a branching
            # find the #endif and add a hash at the end and replace it
            markidx = sline.find(BRANCHING_MARK)
            if markidx == -1:
                raise Exception("No branching mark for branch at line %d!" % idx)
            # replace the symbol/condition by a fake one that we'll define/undefine
            mark = sline[markidx:]
            branchtext = sline.replace("// " + mark, '')
            sline = replace_branch_condition(sline)

            textlines = textlines[:idx] + [sline] + mark_endif(textlines[idx + 1:], mark)
            end_offset = find_endpos(textlines[idx:], mark)
            gcclines = textlines[idx:idx + end_offset]
            # textlines = textlines[:idx] + [sline] + textlines[idx + 1:]
            # of this #if extracting until the mark
            gcc_true, gcc_false = get_branches(gcclines)
            lines_true  = textlines[:idx] + gcc_true + textlines[idx + end_offset + 1:]
            lines_false = textlines[:idx] + gcc_false + textlines[idx + end_offset + 1:]
            changed = True
            break

    if not changed:
        return None, None, None

    return "\n".join(lines_true), "\n".join(lines_false), branchtext


def load_tree(node):
    text_left, text_right, node.branchtext = expand_branch(node.code)
    if not node.branchtext:
        # Restore the includes
        node.code = re.sub("\n+", "\n", node.code.replace("__#__", "#"))

    ontext = "(%s)" % str(node.is_left)
    if node.path:
        node.path[-1] = node.path[-1] + ontext

    if text_left:
        node.left = Tree()
        node.left.path = copy(node.path)
        node.left.code = text_left.replace("\n\n", "\n")
        node.left.is_left = True
        node.left.path.append(node.branchtext)
        load_tree(node.left)

    if text_right:
        node.right = Tree()
        node.right.path = copy(node.path)
        node.right.code = text_right.replace("\n\n", "\n")
        node.right.is_left = False
        node.right.path.append(node.branchtext)
        load_tree(node.right)


def print_tree(node):
    if node is None:
        return

    name = "Node" if node.branchtext else "LeafNode"
    print("====> %s: %s" % (name, " -> ".join(node.path)))
    print(node.code)
    print('-----------')

    print_tree(node.left)
    print_tree(node.right)


def main():
    if len(sys.argv) < 2:
        print("You only had one thing to do! (input file)")
        sys.exit(1)

    inp = sys.argv[1]
    text = open(inp).read()

    root = Tree()
    root.code = disable_other_directives(text)
    root.path = ["ROOT"]
    load_tree(root)
    print_tree(root)


if __name__ == "__main__":
    main()
