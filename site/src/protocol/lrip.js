// F-56: decode an LRIP packet (hex) by a layout from lib/protocol-data.mjs (lripLayout); pure, used by /protocol/ figure 5
// and by tests/protocol-lrip.test.mjs against the golden vectors. Fields wider than 48 bits (the MAC) come back as bit strings.
// big-endian, most significant bit first; signed for type "int"
export function lripDecode(hex, layout) {
  let bits = ''; for (const c of hex) bits += parseInt(c, 16).toString(2).padStart(4, '0');
  if (bits.length !== layout.bits) throw new Error(`packet has ${bits.length} bits, the layout ${layout.bits}`);
  let p = 0;
  return layout.fields.map(f => {
    let v = BigInt('0b' + bits.slice(p, p + f.bits)); p += f.bits;
    if (f.type === 'int' && v >> BigInt(f.bits - 1)) v -= 1n << BigInt(f.bits);
    return f.bits > 48 ? bits.slice(p - f.bits, p) : Number(v);
  });
}

