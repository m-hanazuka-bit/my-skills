# 2D と 3D をシームレスにつなぐ

3D は Blender で透過 PNG に書き出し、HTML の `<img id="img3d">` として 2D の中に重ねる。
つなぎ目は「同じ形・同じ色・同じ位置」を 1 フレームだけ共有させ、その瞬間をビートの頭（キックかインパクト）に置く。
音が大きい瞬間は目がカットを追えないので、多少のズレは消える。

## 基本の 5 パターン

| # | 名前 | 2D → 3D（入り） | 3D → 2D（抜け） | 実装 |
|---|---|---|---|---|
| 1 | **丸で受け渡し**（テンプレ既定） | 2D の丸が中央に縮まる → 同じ位置の 3D 主役に | カメラが主役に突っ込み画面が primary 色で埋まる → 丸が画面を覆って次の 2D へ | template.html の `#shape` と blender_scene.py の `handoff_in/out` |
| 2 | **ドリーズーム**（平面 → 立体） | 超望遠（lens×4、距離×4）で撮ると 3D がほぼ平面に見える＝2D のシルエットと重ねられる。1 小節で標準レンズへ寄せて奥行きが出る | 逆に望遠へ戻して平面化し、2D のシルエットに置き換える | blender_scene.py の `handoff_in`（既定 ON） |
| 3 | **上から → 斜め** | 2D の図（コートや地図、間取り）を真上から描く → 3D でも真上のカメラから始め、傾けてパースを付ける | 3D カメラを真上に戻し、2D の図に差し替え | `camera` を自作：`rig.rotation_euler.x` を 0 → 60° で打つ。2D 側は同じ線幅・同じ色で |
| 4 | **質感を柄にする** | — | 主役（ボール等）に寄って画面が質感で埋まる → その質感を 2D の `pattern` シーン（穴＝円、色＝同じ）にして続ける | template の `type: "pattern"`、`look.pattern_word` |
| 5 | **3D 文字を 2D 面に載せる** | 2D の床（コートのライン等）の上で 3D の押し出し文字が起き上がる | 文字が倒れて 2D のタイトルに重なる | subject `type: "text"`＋和文フォント指定、`camera.move: "static"` |

## 共通ルール
- **パレットを完全に共有**：storyboard の `palette` が Blender のライト色・マテリアルと HTML の CSS 変数の両方に入る。独自の色を足さない
- **光の向きをそろえる**：2D の影・グラデの明るい側と、Blender の Key ライト（右上）を同じ方向に
- **3D の背景は透過**（`transparent: true`）。背景は常に 2D 側が描く → 3D の前後で背景が途切れない
- **切り替えの瞬間は 1〜2 フレームの白フラッシュかワイプを重ねてもよい**（インパクトの頭だけ）
- **カメラの動きの向きを 2D に引き継ぐ**：3D が右回りに回っていたら、次の 2D の要素も右から入れる
- 確認は必ずつなぎ目の前後 ±3 フレームを並べて見る（`render_frames.mjs --from N-3 --to N+3`）

## Blender が使えない / うまくいかないとき（three.js 代替）
3D のモデリングやレンダリングが難しい環境では、three.js を HTML に直接入れて同じ `seek(t)` で描く。
`render_frames.mjs` は WebGL もそのまま撮れる（ヘッドレス Chromium は SwiftShader で描画）。

```html
<canvas id="gl" class="layer"></canvas>
<script type="module">
import * as THREE from "https://cdn.jsdelivr.net/npm/three@0.170.0/build/three.module.js";
const renderer = new THREE.WebGLRenderer({ canvas: document.getElementById("gl"), alpha: true, antialias: true, preserveDrawingBuffer: true });
renderer.setSize(1920, 1080, false);
const scene = new THREE.Scene(), cam = new THREE.PerspectiveCamera(35, 16 / 9, 0.1, 100);
scene.add(new THREE.HemisphereLight(0xffffff, 0x223355, 1.2));
const key = new THREE.DirectionalLight(0xffffff, 2); key.position.set(3, 4, 5); scene.add(key);
const hero = new THREE.Mesh(new THREE.SphereGeometry(1, 64, 32), new THREE.MeshStandardMaterial({ color: getComputedStyle(document.documentElement).getPropertyValue("--accent").trim(), roughness: .45 }));
scene.add(hero);
// 既存の seek を包んで、同じ時刻で 3D も描く（時間から状態を計算する。自走アニメ禁止）
const seek2d = window.seek;
window.seek = async t => {
  await seek2d(t);
  const s3 = TL.scenes.find(x => x.type === "3d"); const on = s3 && t >= s3.start && t < s3.end;
  renderer.domElement.style.display = on ? "block" : "none";
  if (!on) return;
  const k = pulse(t, TL.kicks, .12);
  hero.scale.setScalar(1 + k * .08);
  const ang = (t - s3.start) / spb * 0.15;
  cam.position.set(Math.sin(ang) * 6, 1.5, Math.cos(ang) * 6); cam.lookAt(0, 0, 0);
  renderer.render(scene, cam);
};
</script>
```
- `#gl` は `#img3d` と同じ重なり順（`#shape` の上、`#title` の下）に置く
- オフラインなら `npm i three` して `node_modules/three/build/three.module.js` を相対パスで読む
- 形が複雑なら Blender で GLB だけ作り、three.js の `GLTFLoader` で読むのが中間案
