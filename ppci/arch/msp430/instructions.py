""" Definitions of msp430 instruction set. """

from ..encoding import Instruction, operand, Syntax, Constructor
from ..encoding import FixedPattern, VariablePattern
from ..arch import ArtificialInstruction
from ..isa import Relocation, Isa
from ..token import Token, bit_range, bit
from .registers import Msp430Register, r0, r2, r3, SP, PC
from ...utils.bitfun import align, wrap_negative
from ...ir import i16

# pylint: disable=no-member,invalid-name


isa = Isa()


class Msp430SingleOperandToken(Token):
    def __init__(self):
        super().__init__(16, '<H')

    prefix = bit_range(10, 16)
    opcode = bit_range(7, 10)
    bw = bit(6)
    As = bit_range(4, 6)
    source = bit_range(0, 4)


class Msp430JumpToken(Token):
    def __init__(self):
        super().__init__(16, '<H')

    opcode = bit_range(13, 16)
    condition = bit_range(10, 13)
    offset = bit_range(0, 10)


class Msp430TwoOperandToken(Token):
    def __init__(self):
        super().__init__(16, '<H')

    opcode = bit_range(12, 16)
    source = bit_range(8, 12)
    Ad = bit(7)
    bw = bit(6)
    As = bit_range(4, 6)
    destination = bit_range(0, 4)


class SrcImmToken(Token):
    srcimm = bit_range(0, 16)

    def __init__(self):
        super().__init__(16, '<H')


class DstImmToken(Token):
    dstimm = bit_range(0, 16)

    def __init__(self):
        super().__init__(16, '<H')


# Relocation functions:
@isa.register_relocation
def apply_rel10bit(sym_value, data, reloc_value):
    """ Apply 10 bit signed relocation """
    assert sym_value % 2 == 0
    offset = (sym_value - (align(reloc_value, 2)) - 2) >> 1
    assert offset in range(-511, 511, 1), str(offset)
    imm10 = wrap_negative(offset, 10)
    data[0] = imm10 & 0xff
    cmd = data[1] & 0xfc
    data[1] = cmd | (imm10 >> 8)


@isa.register_relocation
def apply_abs16_imm0(sym_value, data, reloc_value):
    """ Lookup address and assign to 16 bit """
    assert sym_value % 2 == 0
    data[0] = sym_value & 0xff
    data[1] = (sym_value >> 8) & 0xff


@isa.register_relocation
def apply_abs16_imm1(sym_value, data, reloc_value):
    """ Lookup address and assign to 16 bit """
    assert sym_value % 2 == 0
    data[2] = sym_value & 0xff
    data[3] = (sym_value >> 8) & 0xff


@isa.register_relocation
def apply_abs16_imm2(sym_value, data, reloc_value):
    """ Lookup address and assign to 16 bit """
    # TODO: merge this with imm2 variant
    assert sym_value % 2 == 0
    data[4] = sym_value & 0xff
    data[5] = (sym_value >> 8) & 0xff


class Dst(Constructor):
    reg = operand('reg', Msp430Register, write=True)
    imm = operand('imm', int)
    Ad = operand('Ad', int)
    is_reg_target = False
    is_special = False


class RegDst(Dst):
    is_reg_target = True
    syntax = Syntax([Dst.reg])
    patterns = [
        FixedPattern('Ad', 0),
        VariablePattern('destination', Dst.reg),
        ]


class AddrDst(Dst):
    """  absolute address """
    addr = operand('addr', str)
    tokens = [DstImmToken]
    syntax = Syntax(['&', addr])
    is_special = True
    patterns = [
        FixedPattern('Ad', 1),
        FixedPattern('destination', 2),
        ]


class MemDst(Dst):
    """  register offset memory access, for example: 0x88(R8) """
    tokens = [DstImmToken]
    syntax = Syntax([Dst.imm, '(', Dst.reg, ')'])
    patterns = [
        FixedPattern('Ad', 1),
        VariablePattern('destination', Dst.reg),
        VariablePattern('dstimm', Dst.imm),
        ]


dst_modes = (RegDst, AddrDst, MemDst)


class Src(Constructor):
    reg = operand('reg', Msp430Register, read=True)
    imm = operand('imm', int)
    As = operand('As', int)
    is_reg_target = False
    is_special = False


class ConstSrc(Src):
    """ Equivalent to @PC+ """
    tokens = [SrcImmToken]
    syntax = Syntax(['#', Src.imm])
    is_special = True
    patterns = [
        FixedPattern('As', 3),
        FixedPattern('source', 0),
        VariablePattern('srcimm', Src.imm),
        ]


class ConstLabelSrc(Src):
    """ Equivalent to @PC+ """
    addr = operand('addr', str)
    tokens = [SrcImmToken]
    syntax = Syntax(['#', addr])
    is_special = True
    patterns = [
        FixedPattern('As', 3),
        FixedPattern('source', 0),
        ]
    # TODO: reloc here? this should be implemented something like this:
    relocations = (
        Relocation(addr, apply_abs16_imm0),
    )


as_cn_map = {-1: 3, 0: 0, 1: 1, 2: 2, 4: 2, 8: 3}
rg_cn_map = {-1: 3, 0: 3, 1: 3, 2: 3, 4: 2, 8: 2}


class SmallConstSrc(Src):
    """ Equivalent to @PC+ """
    syntax = Syntax(['#', Src.imm], priority=2)
    # TODO: implement small source!
    is_special = True
    patterns = [
        VariablePattern(
            'As', Src.imm, transform=(lambda x: as_cn_map[x], None)),
        VariablePattern(
            'source', Src.imm, transform=(lambda x: rg_cn_map[x], None)),
        ]


def small_const_src(x):
    """ Helper to generate small integer constants """
    assert x in (-1, 0, 1, 2, 4, 8)
    if x == -1:
        return SmallConstSrc(-1, reg=r3, As=3)
    elif x == 0:
        return SmallConstSrc(0, reg=r3, As=0)
    elif x == 1:
        return SmallConstSrc(1, reg=r3, As=1)
    elif x == 2:
        return SmallConstSrc(2, reg=r3, As=2)
    elif x == 4:
        return SmallConstSrc(4, reg=r2, As=2)
    elif x == 8:
        return SmallConstSrc(8, reg=r2, As=3)
    else:
        raise NotImplementedError()


class RegSrc(Src):
    """ Simply refer to a register """
    is_reg_target = True
    syntax = Syntax([Src.reg])
    patterns = [
        FixedPattern('As', 0),
        VariablePattern('source', Src.reg),
        ]


class AdrSrc(Src):
    """ absolute address """
    is_special = True
    addr = operand('addr', str)
    tokens = [SrcImmToken]
    syntax = Syntax(['&', addr])
    patterns = [
        FixedPattern('As', 1),
        FixedPattern('source', 2),
        ]


class MemSrc(Src):
    """ Memory content """
    syntax = Syntax(['@', Src.reg])
    patterns = [
        FixedPattern('As', 2),
        VariablePattern('source', Src.reg),
        ]


class MemSrcInc(Src):
    """ Memory content post increment """
    syntax = Syntax(['@', Src.reg, '+'])
    patterns = [
        FixedPattern('As', 3),
        VariablePattern('source', Src.reg),
        ]


class MemSrcOffset(Src):
    tokens = [SrcImmToken]
    syntax = Syntax([Src.imm, '(', Src.reg, ')'])
    patterns = [
        FixedPattern('As', 1),
        VariablePattern('source', Src.reg),
        VariablePattern('srcimm', Src.imm),
        ]


src_modes = (
    AdrSrc, RegSrc, MemSrc, MemSrcInc, MemSrcOffset,
    SmallConstSrc, ConstSrc, ConstLabelSrc)


class Msp430Instruction(Instruction):
    isa = isa


#########################
# Jump instructions:
#########################

class JumpInstruction(Msp430Instruction):
    tokens = [Msp430JumpToken]

    def relocations(self):
        yield (self.target, apply_rel10bit)


def create_jump_instruction(name, condition):
    target = operand('target', str)
    syntax = Syntax([name, ' ', target])
    patterns = [
        FixedPattern('condition', condition),
        FixedPattern('opcode', 1),
        # RelocPattern('offset', target, lambda sv, rv: ),
        ]
    members = {
        'syntax': syntax, 'target': target, 'patterns': patterns}
    return type(name + '_ins', (JumpInstruction, ), members)


Jne = create_jump_instruction('jne', 0)
Jnz = create_jump_instruction('jnz', 0)
Jeq = create_jump_instruction('jeq', 1)
Jz = create_jump_instruction('jz', 1)
Jnc = create_jump_instruction('jnc', 2)
Jc = create_jump_instruction('jc', 3)
Jn = create_jump_instruction('jn', 4)
Jge = create_jump_instruction('jge', 5)
Jl = create_jump_instruction('jl', 6)
Jmp = create_jump_instruction('jmp', 7)


#########################
# Single operand arithmatic:
#########################


class OneOpArith(Msp430Instruction):
    tokens = [Msp430SingleOperandToken]

    def relocations(self):
        # TODO: re design this:
        if hasattr(self.src, 'addr'):
            yield (self.src.addr, apply_abs16_imm1)


def one_op_instruction(mne, opcode, b=0, src_write=True):
    """ Helper function to define a one operand arithmetic instruction """
    src = operand('src', src_modes)
    patterns = [
        FixedPattern('prefix', 0b000100),
        FixedPattern('opcode', opcode),
        FixedPattern('bw', b)
        ]
    if b:
        syntax = Syntax([mne, '.', 'b', ' ', src])
        class_name = mne + 'b'
    else:
        syntax = Syntax([mne, ' ', src])
        class_name = mne
    members = {
        'opcode': opcode, 'syntax': syntax, 'src': src, 'patterns': patterns}
    return type(class_name.title(), (OneOpArith,), members)


def make_one_op_base(mne, opcode, b=0):
    members = {
        'tokens': [Msp430SingleOperandToken],
        'patterns': [
            FixedPattern('prefix', 0b000100),
            FixedPattern('opcode', opcode),
            FixedPattern('bw', b),
            ],
        'syntax': Syntax([mne, ' '])
        }
    return type(mne.title(), (Instruction,), members)


class MemByReg(Instruction):
    """ Memory content """
    reg = operand('reg', Msp430Register, read=True)
    tokens = []
    patterns = [
        FixedPattern('As', 2),
        VariablePattern('source', reg),
        ]
    syntax = Syntax(['@', reg])


Rrcw = one_op_instruction('rrc', 0, b=0)
Rrcb = one_op_instruction('rrc', 0, b=1)
Swpb = one_op_instruction('swpb', 1)
Rraw = one_op_instruction('rra', 2, b=0)
Rrab = one_op_instruction('rra', 2, b=1)

# Sxt = one_op_instruction('sxt', 3)
SxtBase = make_one_op_base('sxt', 3)
SxtMemByReg = SxtBase + MemByReg
isa.add_instruction(SxtMemByReg)

Push = one_op_instruction('push', 4, src_write=False)
Call = one_op_instruction('call', 5, src_write=False)


class Reti(Msp430Instruction):
    tokens = [SrcImmToken]
    syntax = Syntax(['reti'])

    def encode(self):
        tokens = self.get_tokens()
        tokens[0][0:16] = 0x1300
        return tokens.encode()


#########################
# Two operand arithmatic instructions:
#########################


class TwoOpArithInstruction(Msp430Instruction):
    tokens = [Msp430TwoOperandToken]

    def relocations(self):
        if hasattr(self.src, 'addr'):
            yield (self.src.addr, apply_abs16_imm1)
        if hasattr(self.dst, 'addr'):
            if hasattr(self.src, 'addr'):
                yield (self.dst.addr, apply_abs16_imm2)
            else:
                yield (self.dst.addr, apply_abs16_imm1)

    @property
    def used_registers(self):
        s = []
        # Source:
        if not self.src.is_special:
            if self.src.is_reg_target:
                s.append(self.src.reg)
            else:
                s.append(self.src.reg)

        # Dst:
        if not self.dst.is_special:
            if self.dst.is_reg_target:
                if self.dst_read:
                    s.append(self.dst.reg)
            else:
                s.append(self.dst.reg)
        s.extend(self.extra_uses)
        return s

    @property
    def defined_registers(self):
        s = []
        if self.dst.is_reg_target and not self.dst.is_special:
            if self.dst_write:
                s.append(self.dst.reg)
        s.extend(self.extra_defs)
        return s


def two_op_ins(mne, opc, b=0, dst_read=True, dst_write=True):
    """ Helper function to define a two operand arithmetic instruction """
    src = operand('src', src_modes)
    dst = operand('dst', dst_modes)
    if b:
        syntax = Syntax([mne, '.', 'b', ' ', src, ',', ' ', dst])
        class_name = mne + 'b'
    else:
        syntax = Syntax([mne, '.', 'w', ' ', src, ',', ' ', dst])
        class_name = mne + 'w'
    patterns = [
        FixedPattern('opcode', opc),
        FixedPattern('bw', b),
        ]
    members = {
        'patterns': patterns, 'src': src, 'dst': dst, 'syntax': syntax,
        'dst_read': dst_read, 'dst_write': dst_write
        }
    return type(class_name.title(), (TwoOpArithInstruction,), members)


Mov = two_op_ins('mov', 4, dst_read=False)
Movb = two_op_ins('mov', 4, b=1, dst_read=False)
Add = two_op_ins('add', 5)
Addc = two_op_ins('addc', 6)
Subc = two_op_ins('subc', 7)
Sub = two_op_ins('sub', 8)
Cmp = two_op_ins('cmp', 9, dst_write=False)
Cmpb = two_op_ins('cmp', 9, b=1, dst_write=False)
Dadd = two_op_ins('dadd', 10)
Bit = two_op_ins('bit', 11, dst_write=False)
Bitb = two_op_ins('bit', 11, b=1, dst_write=False)
Bicw = two_op_ins('bic', 12)
Bicb = two_op_ins('bic', 12, b=1)
Bisw = two_op_ins('bis', 13)
Bisb = two_op_ins('bis', 13, b=1)
Xor = two_op_ins('xor', 14)
Xorb = two_op_ins('xor', 14, b=1)
And = two_op_ins('and', 15)
Andb = two_op_ins('and', 15, b=1)


# pseudo instructions:


class PseudoMsp430Instruction(ArtificialInstruction):
    """ Base class for all pseudo instructions """
    isa = isa


class Ret(PseudoMsp430Instruction):
    """ Pop value from stack """
    syntax = Syntax(['ret'])

    def render(self):
        yield Pop(PC)


class Pop(PseudoMsp430Instruction):
    """ Pop value from stack """
    dst = operand('dst', Msp430Register, write=True)
    syntax = Syntax(['pop', ' ', dst])

    def render(self):
        yield Mov(MemSrcInc(SP), RegDst(self.dst))


class Nop(PseudoMsp430Instruction):
    """ no op implemented as mov #0, r3 """
    syntax = Syntax(['nop'])

    def render(self):
        yield Mov(small_const_src(0), RegDst(r3))


class Clrc(PseudoMsp430Instruction):
    """ clear carry implemented as bic #1, sr """
    syntax = Syntax(['clrc'])

    def render(self):
        yield Bicw(small_const_src(1), RegDst(r2))


class Clrn(PseudoMsp430Instruction):
    """ clear negative implemented as bic #4, sr """
    syntax = Syntax(['clrn'])

    def render(self):
        yield Bicw(small_const_src(4), RegDst(r2))


class Clrz(PseudoMsp430Instruction):
    """ clear zero implemented as bic #2, sr """
    syntax = Syntax(['clrz'])

    def render(self):
        yield Bicw(small_const_src(2), RegDst(r2))


def push(reg):
    """ Push register helper """
    return Push(RegSrc(reg))


def call(label):
    assert isinstance(label, str)
    return Call(ConstLabelSrc(label))


def mov(src, dst):
    """ Register to register move """
    return Mov(RegSrc(src), RegDst(dst), ismove=True)


# -- for instruction selection:

@isa.pattern('stm', 'JMP', size=4)
def pattern_jmp(self, tree):
    tgt = tree.value
    self.emit(Jmp(tgt.name, jumps=[tgt]))


@isa.pattern('stm', 'CJMP(reg, reg)', size=10)
def pattern_cjmp(context, tree, lhs, rhs):
    op, true_tgt, false_tgt = tree.value
    opnames = {"<": Jl, ">": Jl, "==": Jz, "!=": Jne, ">=": Jge}
    op_ins = opnames[op]
    if op in ['>']:
        # Swap operands here!
        # This is really hairy code, but it should work!
        lhs, rhs = rhs, lhs
    jmp_ins = Jmp(false_tgt.name, jumps=[false_tgt])
    # cmp does a dummy dst - src
    context.emit(Cmp(RegSrc(rhs), RegDst(lhs)))
    context.emit(op_ins(true_tgt.name, jumps=[true_tgt, jmp_ins]))
    context.emit(jmp_ins)


@isa.pattern('reg', 'MOVI16(reg)', size=2)
def pattern_mov16(self, tree, c0):
    dst = tree.value
    self.emit(mov(c0, dst))


@isa.pattern('reg', 'MOVI8(reg)', size=2)
def pattern_mov8(self, tree, c0):
    dst = tree.value
    self.emit(mov(c0, dst))


@isa.pattern('reg', 'CONSTI16', size=4)
def pattern_const16(self, tree):
    dst = self.new_reg(Msp430Register)
    cnst = tree.value
    self.emit(Mov(ConstSrc(cnst), RegDst(dst)))
    return dst


@isa.pattern('reg', 'CONSTI8', size=4)
def pattern_const8(self, tree):
    dst = self.new_reg(Msp430Register)
    cnst = tree.value
    self.emit(Mov(ConstSrc(cnst), RegDst(dst)))
    return dst


@isa.pattern('reg', 'REGI16', size=0, cycles=0, energy=0)
def pattern_reg16(self, tree):
    return tree.value


@isa.pattern('reg', 'REGI8', size=0, cycles=0, energy=0)
def pattern_reg8(self, tree):
    return tree.value


@isa.pattern('reg', 'I16TOI16(reg)', size=0, cycles=0, energy=0)
def pattern_i16toi16(self, tree, c0):
    return c0


@isa.pattern('reg', 'I16TOI8(reg)', size=0, cycles=0, energy=0)
def pattern_i16toi8(self, tree, c0):
    # TODO: do something here?
    return c0


@isa.pattern('reg', 'CALL')
def pattern_call(context, tree):
    return context.gen_call(tree.value)


@isa.pattern('reg', 'MULI16(reg, reg)', size=10)
def pattern_mul16(context, tree, c0, c1):
    d = context.new_reg(Msp430Register)
    context.gen_call(('msp430_runtime___mul', [i16, i16], i16, [c0, c1], d))
    return d


@isa.pattern('reg', 'DIVI16(reg, reg)', size=10)
def pattern_div16(context, tree, c0, c1):
    d = context.new_reg(Msp430Register)
    context.gen_call(('msp430_runtime___div', [i16, i16], i16, [c0, c1], d))
    return d


@isa.pattern('reg', 'ANDI16(reg, reg)', size=4)
def pattern_and16(context, tree, c0, c1):
    dst = context.new_reg(Msp430Register)
    context.emit(mov(c0, dst))
    context.emit(And(RegSrc(c1), RegDst(dst)))
    return dst


@isa.pattern('reg', 'ORI16(reg, reg)', size=4)
def pattern_or16(context, tree, c0, c1):
    dst = context.new_reg(Msp430Register)
    context.emit(mov(c0, dst))
    context.emit(Bisw(RegSrc(c1), RegDst(dst)))
    return dst


@isa.pattern('reg', 'SHRI16(reg, reg)', size=4)
def pattern_shr16(context, tree, c0, c1):
    d = context.new_reg(Msp430Register)
    context.gen_call(('__shr', [i16, i16], i16, [c0, c1], d))
    return d


@isa.pattern('reg', 'SHLI16(reg, reg)', size=4)
def pattern_shl16(context, tree, c0, c1):
    d = context.new_reg(Msp430Register)
    context.gen_call(('__shl', [i16, i16], i16, [c0, c1], d))
    return d


@isa.pattern('reg', 'ADDI16(reg, reg)', size=4)
def pattern_add16(context, tree, c0, c1):
    d = context.new_reg(Msp430Register)
    context.emit(mov(c0, d))
    context.emit(Add(RegSrc(c1), RegDst(d)))
    return d


@isa.pattern('reg', 'SUBI16(reg, reg)', size=4)
def pattern_sub16(context, tree, c0, c1):
    d = context.new_reg(Msp430Register)
    context.emit(mov(c0, d))
    context.emit(Sub(RegSrc(c1), RegDst(d)))
    return d


@isa.pattern('stm', 'STRI16(reg, reg)', size=2)
def pattern_str16(context, tree, c0, c1):
    context.emit(Mov(RegSrc(c1), MemDst(0, c0)))


@isa.pattern('stm', 'STRI8(reg, reg)', size=2)
def pattern_str8(context, tree, c0, c1):
    context.emit(Movb(RegSrc(c1), MemDst(0, c0)))


@isa.pattern('reg', 'LDRI16(reg)', size=2)
def pattern_ldr16(context, tree, c0):
    d = context.new_reg(Msp430Register)
    context.emit(Mov(MemSrc(c0), RegDst(d)))
    return d


@isa.pattern('reg', 'LDRI8(reg)', size=2)
def pattern_ldr8(context, tree, c0):
    d = context.new_reg(Msp430Register)
    context.emit(Movb(MemSrc(c0), RegDst(d)))
    return d


@isa.pattern('reg', 'LABEL', size=2)
def pattern_label(context, tree):
    d = context.new_reg(Msp430Register)
    ln = context.frame.add_constant(tree.value)
    context.emit(Mov(AdrSrc(ln), RegDst(d)))
    return d
