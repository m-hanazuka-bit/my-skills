// 家庭内序列5位パパ — キャラクター（SVG）
// Chars.svg(id, {expr, pose, outfit}) は 200x300 の座標で描く（足元の中心 = (100, 300)）。
// Chars.place(id, x, y, scale, opts) は足元の中心を (x, y) に置いた <g> を返す。
(function () {
  const INK = "#2d2a32";
  const SKIN = "#ffdcbf";
  const CHEEK = "#ffaaa0";

  const CAST = {
    papa:   { name: "パパ",   rank: 5, hair: "#2b2b33", glasses: "#26262c", skin: SKIN },
    tsuma:  { name: "妻",     rank: 1, hair: "#6b3e26", skin: SKIN },
    musuko: { name: "息子",   rank: 2, hair: "#2a2320", skin: SKIN, scale: 0.8 },
    ane:    { name: "義姉",   rank: 3, hair: "#3b2a2e", glasses: "#d0306b", skin: SKIN },
    gifu:   { name: "義父",   rank: 4, hair: "#f4f4f2", skin: "#f8d4b6" },
    kohai:  { name: "年下上司", rank: 0, hair: "#8a5a34", skin: SKIN },  // 会社の上司（元後輩・年下）
  };

  // 服（outfit）ごとの色
  const OUTFITS = {
    suit:    { top: "#3d4f7a", bottom: "#2f3d60", shoe: "#2a2a2a" },
    suitGray:{ top: "#8e96a3", bottom: "#6f7784", shoe: "#5a3a2a" },
    pajama:  { top: "#9cc8e8", bottom: "#86b6da", shoe: "#d9d9d9", stripe: "#ffffff" },
    apron:   { top: "#e86a5a", bottom: "#5a6b8c", shoe: "#8a5a44", apron: "#fff8ef" },
    tshirt:  { top: "#f39a2b", bottom: "#3f7ec9", shoe: "#e04b3c" },
    oshi:    { top: "#a678dd", bottom: "#4a4a62", shoe: "#ffffff" },
    cardigan:{ top: "#c9a86a", bottom: "#6d5a4a", shoe: "#4a3a30", inner: "#f2ece0" },
  };
  const DEFAULT_OUTFIT = { papa: "suit", tsuma: "apron", musuko: "tshirt", ane: "oshi", gifu: "cardigan", kohai: "suitGray" };
  const DEFAULT_EXPR = { papa: "tired", tsuma: "strong", musuko: "smug", ane: "normal", gifu: "gentle", kohai: "normal" };

  // ---- 部品 ----
  function legs(o, short) {
    const h = short ? 30 : 38;
    return `
      <rect x="74" y="${282 - h}" width="22" height="${h}" rx="8" fill="${o.bottom}" stroke="${INK}" stroke-width="4"/>
      <rect x="104" y="${282 - h}" width="22" height="${h}" rx="8" fill="${o.bottom}" stroke="${INK}" stroke-width="4"/>
      <ellipse cx="82" cy="288" rx="18" ry="10" fill="${o.shoe}" stroke="${INK}" stroke-width="4"/>
      <ellipse cx="118" cy="288" rx="18" ry="10" fill="${o.shoe}" stroke="${INK}" stroke-width="4"/>`;
  }

  function arms(o, pose, skin) {
    // 肩 (66,170) / (134,170) から手の位置へ
    const P = {
      down:  [[52, 236], [148, 236]],
      droop: [[60, 244], [140, 244]],
      up:    [[38, 112], [162, 112]],
      hold:  [[88, 214], [112, 214]],
      point: [[52, 236], [176, 150]],
      wave:  [[52, 236], [168, 118]],
    }[pose] || [[52, 236], [148, 236]];
    const arm = (sx, [hx, hy]) => `
      <path d="M${sx} 172 L${hx} ${hy}" stroke="${INK}" stroke-width="24" stroke-linecap="round"/>
      <path d="M${sx} 172 L${hx} ${hy}" stroke="${o.top}" stroke-width="16" stroke-linecap="round"/>
      <circle cx="${hx}" cy="${hy}" r="11" fill="${skin}" stroke="${INK}" stroke-width="4"/>`;
    return arm(68, P[0]) + arm(132, P[1]);
  }

  function torso(id, o) {
    let s = `<path d="M62 176 Q62 154 84 151 L116 151 Q138 154 138 176 L141 252 Q100 260 59 252 Z" fill="${o.top}" stroke="${INK}" stroke-width="5" stroke-linejoin="round"/>`;
    if (o === OUTFITS.suit || o === OUTFITS.suitGray) {
      s += `<path d="M86 152 L100 186 L114 152 Z" fill="#fff" stroke="${INK}" stroke-width="3"/>
            <path d="M100 160 L95 192 L100 202 L105 192 Z" fill="#c0392b" stroke="${INK}" stroke-width="3"/>
            <path d="M84 152 L100 186 L92 200 M116 152 L100 186 L108 200" fill="none" stroke="${INK}" stroke-width="3"/>`;
    } else if (o === OUTFITS.pajama) {
      for (let x = 72; x <= 128; x += 14) s += `<line x1="${x}" y1="158" x2="${x}" y2="252" stroke="${o.stripe}" stroke-width="4" opacity=".7"/>`;
      s += `<circle cx="100" cy="176" r="3" fill="${INK}"/><circle cx="100" cy="200" r="3" fill="${INK}"/><circle cx="100" cy="224" r="3" fill="${INK}"/>`;
    } else if (o === OUTFITS.apron) {
      s += `<path d="M76 186 L124 186 L128 254 Q100 260 72 254 Z" fill="${o.apron}" stroke="${INK}" stroke-width="4"/>
            <path d="M80 186 L88 154 M120 186 L112 154" stroke="${o.apron}" stroke-width="6"/>
            <rect x="90" y="214" width="20" height="16" rx="3" fill="none" stroke="#e8b7a0" stroke-width="3"/>`;
    } else if (o === OUTFITS.oshi) {
      s += `<path d="M100 222 C82 206 82 186 96 188 Q100 189 100 196 Q100 189 104 188 C118 186 118 206 100 222 Z" fill="#ff5fa2" stroke="${INK}" stroke-width="3"/>
            <text x="100" y="212" font-size="16" font-weight="900" text-anchor="middle" fill="#fff" font-family="var(--round)">推</text>`;
    } else if (o === OUTFITS.cardigan) {
      s += `<path d="M90 152 L100 250 L110 152 Z" fill="${o.inner}" stroke="${INK}" stroke-width="3"/>
            <circle cx="92" cy="190" r="3.5" fill="${INK}"/><circle cx="94" cy="214" r="3.5" fill="${INK}"/><circle cx="96" cy="238" r="3.5" fill="${INK}"/>`;
    } else if (o === OUTFITS.tshirt) {
      s += `<text x="100" y="214" font-size="28" font-weight="900" text-anchor="middle" fill="#fff" font-family="var(--round)">10</text>`;
    }
    return s;
  }

  function hairBack(id, c) {
    if (id === "tsuma") return `<path d="M36 146 Q26 40 100 34 Q174 40 164 146 Q150 154 136 146 L64 146 Q50 154 36 146 Z" fill="${c.hair}" stroke="${INK}" stroke-width="5"/>`;
    if (id === "ane") return `<path d="M38 210 Q26 40 100 34 Q174 40 162 210 Q100 222 38 210 Z" fill="${c.hair}" stroke="${INK}" stroke-width="5"/>`;
    return "";
  }

  function hairFront(id, c) {
    switch (id) {
      case "papa":
        return `<path d="M42 98 Q36 38 100 36 Q164 38 158 98 Q152 72 132 66 Q116 74 100 66 Q82 74 68 66 Q48 74 42 98 Z" fill="${c.hair}" stroke="${INK}" stroke-width="5" stroke-linejoin="round"/>
                <path d="M104 38 Q112 14 128 18" fill="none" stroke="${INK}" stroke-width="5" stroke-linecap="round"/>`;
      case "tsuma":
        return `<path d="M40 104 Q38 40 100 38 Q162 40 160 104 L150 106 Q148 80 138 76 L62 76 Q52 80 50 106 Z" fill="${c.hair}" stroke="${INK}" stroke-width="5" stroke-linejoin="round"/>`;
      case "musuko":
        return `<path d="M42 96 L36 62 L56 70 L58 40 L78 58 L92 30 L104 56 L124 32 L130 60 L152 46 L148 72 L166 70 L158 98 Q140 74 100 72 Q60 74 42 96 Z" fill="${c.hair}" stroke="${INK}" stroke-width="5" stroke-linejoin="round"/>`;
      case "ane":
        return `<path d="M40 110 Q38 40 100 38 Q162 40 160 110 Q150 84 124 80 Q118 92 100 90 Q84 92 78 80 Q50 84 40 110 Z" fill="${c.hair}" stroke="${INK}" stroke-width="5" stroke-linejoin="round"/>`;
      case "kohai":
        return `<path d="M40 100 Q36 36 104 36 Q164 40 160 100 Q150 70 120 64 Q110 82 70 72 Q50 78 40 100 Z" fill="${c.hair}" stroke="${INK}" stroke-width="5" stroke-linejoin="round"/>`;
      case "gifu":
        return `<path d="M42 110 Q36 66 54 56 Q62 74 58 104 Z M158 110 Q164 66 146 56 Q138 74 142 104 Z" fill="${c.hair}" stroke="${INK}" stroke-width="4" stroke-linejoin="round"/>
                <path d="M58 62 Q80 36 112 40 Q144 44 148 64 Q120 50 90 56 Q70 60 58 62 Z" fill="${c.hair}" stroke="${INK}" stroke-width="4" stroke-linejoin="round"/>`;
    }
    return "";
  }

  function face(id, expr) {
    const L = 78, R = 122, Y = 106;
    const eye = (x, y = Y) => `<ellipse cx="${x}" cy="${y}" rx="6" ry="8" fill="${INK}"/><circle cx="${x + 2}" cy="${y - 3}" r="2" fill="#fff"/>`;
    const brow = (x1, y1, x2, y2) => `<path d="M${x1} ${y1} L${x2} ${y2}" stroke="${INK}" stroke-width="4.5" stroke-linecap="round"/>`;
    let s = `<ellipse cx="64" cy="126" rx="10" ry="6" fill="${CHEEK}" opacity=".55"/><ellipse cx="136" cy="126" rx="10" ry="6" fill="${CHEEK}" opacity=".55"/>`;
    switch (expr) {
      case "tired":
        s += `<path d="M68 106 L88 106 M112 106 L132 106" stroke="${INK}" stroke-width="5" stroke-linecap="round"/>
              <path d="M70 101 Q78 98 86 101 M114 101 Q122 98 130 101" fill="none" stroke="${INK}" stroke-width="3"/>
              <path d="M70 116 Q78 120 86 116 M114 116 Q122 120 130 116" fill="none" stroke="#9a8fb0" stroke-width="3"/>
              <path d="M92 136 Q100 132 108 136" fill="none" stroke="${INK}" stroke-width="4" stroke-linecap="round"/>`;
        break;
      case "sad":
        s += eye(L, Y + 2) + eye(R, Y + 2) + brow(66, 92, 88, 86) + brow(112, 86, 134, 92)
          + `<path d="M88 138 Q94 132 100 136 Q106 140 112 134" fill="none" stroke="${INK}" stroke-width="4" stroke-linecap="round"/>
             <path d="M70 116 Q64 128 70 134 Q76 128 70 116 Z" fill="#7cc4f2" stroke="${INK}" stroke-width="2"/>`;
        break;
      case "cry":
        s += `<path d="M68 104 Q78 96 88 104 M112 104 Q122 96 132 104" fill="none" stroke="${INK}" stroke-width="5" stroke-linecap="round"/>`
          + brow(66, 90, 88, 84) + brow(112, 84, 134, 90)
          + `<path d="M72 110 L70 150 M128 110 L130 150" stroke="#7cc4f2" stroke-width="7" stroke-linecap="round"/>
             <path d="M88 136 Q100 128 112 136" fill="none" stroke="${INK}" stroke-width="4" stroke-linecap="round"/>`;
        break;
      case "shock":
        s += `<circle cx="${L}" cy="${Y}" r="13" fill="#fff" stroke="${INK}" stroke-width="4"/><circle cx="${L}" cy="${Y}" r="3.5" fill="${INK}"/>
              <circle cx="${R}" cy="${Y}" r="13" fill="#fff" stroke="${INK}" stroke-width="4"/><circle cx="${R}" cy="${Y}" r="3.5" fill="${INK}"/>
              <ellipse cx="100" cy="140" rx="9" ry="12" fill="${INK}"/>
              <path d="M70 60 L70 80 M84 56 L84 78 M98 54 L98 76" stroke="#5b7bd5" stroke-width="4" stroke-linecap="round" opacity=".8"/>`;
        break;
      case "happy":
        s += `<path d="M68 110 Q78 96 88 110 M112 110 Q122 96 132 110" fill="none" stroke="${INK}" stroke-width="5" stroke-linecap="round"/>
              <path d="M86 130 Q100 150 114 130 Z" fill="#c9433c" stroke="${INK}" stroke-width="4" stroke-linejoin="round"/>`;
        break;
      case "gentle":
        s += `<path d="M68 108 Q78 98 88 108 M112 108 Q122 98 132 108" fill="none" stroke="${INK}" stroke-width="4.5" stroke-linecap="round"/>
              <path d="M88 134 Q100 144 112 134" fill="none" stroke="${INK}" stroke-width="4" stroke-linecap="round"/>`;
        break;
      case "smug":
        s += `<path d="M68 104 L88 104 M112 104 L132 104" stroke="${INK}" stroke-width="4.5" stroke-linecap="round"/>
              <ellipse cx="${L + 2}" cy="${Y + 3}" rx="5" ry="5" fill="${INK}"/><ellipse cx="${R + 2}" cy="${Y + 3}" rx="5" ry="5" fill="${INK}"/>
              <path d="M90 134 Q104 142 114 128" fill="none" stroke="${INK}" stroke-width="4" stroke-linecap="round"/>`;
        break;
      case "strong":
        s += eye(L) + eye(R) + brow(66, 86, 88, 92) + brow(112, 92, 134, 86)
          + `<path d="M90 134 Q100 140 110 134" fill="none" stroke="${INK}" stroke-width="4" stroke-linecap="round"/>`;
        break;
      case "sleep":
        s += `<path d="M68 106 Q78 114 88 106 M112 106 Q122 114 132 106" fill="none" stroke="${INK}" stroke-width="4.5" stroke-linecap="round"/>
              <ellipse cx="100" cy="138" rx="5" ry="4" fill="${INK}"/>`;
        break;
      default: // normal
        s += eye(L) + eye(R) + `<path d="M90 132 Q100 140 110 132" fill="none" stroke="${INK}" stroke-width="4" stroke-linecap="round"/>`;
    }
    if (id === "gifu") {
      // 白い眉と目尻のしわ、口ひげ
      s += `<path d="M66 90 Q78 84 90 90 M110 90 Q122 84 134 90" fill="none" stroke="#e6e6e2" stroke-width="7" stroke-linecap="round"/>
            <path d="M58 104 L52 100 M58 110 L51 110 M142 104 L148 100 M142 110 L149 110" stroke="#c99a7e" stroke-width="2.5" stroke-linecap="round"/>
            <path d="M84 124 Q92 118 100 124 Q108 118 116 124 Q108 130 100 126 Q92 130 84 124 Z" fill="#f4f4f2" stroke="${INK}" stroke-width="3"/>`;
    }
    return s;
  }

  function glasses(color) {
    return `<g fill="rgba(255,255,255,.18)" stroke="${color}" stroke-width="5">
      <rect x="60" y="92" width="36" height="28" rx="9"/><rect x="104" y="92" width="36" height="28" rx="9"/>
      <path d="M96 104 Q100 100 104 104" fill="none"/><path d="M60 102 L44 98 M140 102 L156 98" fill="none"/></g>`;
  }

  function svg(id, opts = {}) {
    const c = CAST[id];
    const o = OUTFITS[opts.outfit || DEFAULT_OUTFIT[id]];
    const expr = opts.expr || DEFAULT_EXPR[id];
    const pose = opts.pose || "down";
    return `<g>
      ${hairBack(id, c)}
      ${legs(o, id === "musuko")}
      ${torso(id, o)}
      ${arms(o, pose, c.skin)}
      <circle cx="40" cy="110" r="11" fill="${c.skin}" stroke="${INK}" stroke-width="4"/>
      <circle cx="160" cy="110" r="11" fill="${c.skin}" stroke="${INK}" stroke-width="4"/>
      <circle cx="100" cy="100" r="60" fill="${c.skin}" stroke="${INK}" stroke-width="5"/>
      ${face(id, expr)}
      ${c.glasses ? glasses(c.glasses) : ""}
      ${hairFront(id, c)}
      ${opts.extra || ""}
    </g>`;
  }

  // 顔だけ（序列ボードなど用）。中心 (100,100)、半径 60 の円に収まる
  function head(id, opts = {}) {
    const c = CAST[id];
    const expr = opts.expr || DEFAULT_EXPR[id];
    return `<g>${hairBack(id, c).replace(/210/g, "150")}
      <circle cx="100" cy="100" r="60" fill="${c.skin}" stroke="${INK}" stroke-width="5"/>
      ${face(id, expr)}${c.glasses ? glasses(c.glasses) : ""}${hairFront(id, c)}</g>`;
  }

  function place(id, x, y, s = 1, opts = {}) {
    const k = s * (CAST[id].scale || 1);
    const flip = opts.flip ? -1 : 1;
    return `<g transform="translate(${x} ${y}) scale(${k * flip} ${k}) rotate(${opts.rot || 0}) translate(-100 -300)">${svg(id, opts)}</g>`;
  }

  function placeHead(id, x, y, s = 1, opts = {}) {
    return `<g transform="translate(${x} ${y}) scale(${s}) translate(-100 -100)">${head(id, opts)}</g>`;
  }

  window.Chars = { CAST, svg, head, place, placeHead, INK };
})();
