# assembly_video — анімована інструкція зі збірки v3 (укр.)

Відео ~104 с (1920×1080, 30 к/с): 3D-анімація реальних моделей v3 (струбцина, тримач, носій, шпиндель, конус, ручка, гайка, гвинт, накладка, рулон, стіл), українські підписи, 10 нумерованих кроків, схема відстані між тримачами. Зібрано в **HyperFrames** (HTML + GSAP → MP4), 3D малює **three.js**.

> Файл відео: `out/stretch_dispenser_assembly_v3.mp4` (створюється командою `npm run render`; у git не зберігається).

## Швидкий старт (на своєму ПК)

Потрібно: Node.js ≥ 22 і FFmpeg (`ffmpeg -version`). Chrome для рендеру HyperFrames завантажить сам при першому запуску (`npx hyperframes browser ensure`).

```bash
cd projects/stretch_dispenser/assembly_video
npm install
npm run preview      # студія з таймлайном у браузері
npm run render       # out/stretch_dispenser_assembly_v3.mp4 (стандартна якість)
npm run render:draft # швидкий чорновий рендер
```

## Структура (для ШІ-агентів)

```yaml
src/steps.js        # ЄДИНЕ джерело: час сцен (t0, dur), українські тексти, траєкторія камери CAMS
src/scene.js        # three.js-сцена як чиста функція часу: GuideScene.update(t) ставить усі позиції/повороти/підсвітку/підписи
assets/parts.json   # 9 деталей лівого вузла в світових координатах збірки (float32 + uint32, zlib+base64), згенеровано export_assets.py
assets/layout.json  # числа збірки (положення осі, рулону, відстань між тримачами)
build.mjs           # esbuild-бандл dist/scene.js + генерація index.html з steps.js (не редагуйте index.html вручну)
index.html          # композиція HyperFrames (root data-composition-id="main", одна пауза-шкала window.__timelines.main)
export_assets.py    # python (з venv проєкту): перебудовує assets/ з ../v3_spindle/check.py; параметри W=530 ID=46 sigma=16
vendor/gsap.min.js  # локальний GSAP (без CDN, детермінований рендер)
```

Як змінити:
- **Текст, тривалість, порядок кроків:** `src/steps.js` (`SCENES`), далі `npm run build`.
- **Камера:** `CAMS` у `src/steps.js` (`[t, позиція, ціль]`, мм, вісь Y вгору). Перегляд кадрів: `npx hyperframes snapshot --at 10,40,80`.
- **Рух деталей:** `SPEC` у `src/scene.js` (`kf: [t, [dx,dy,dz], обертів]`, зсув від фінального положення). Різьбові деталі обертаються за правилом правої різьби: рух уздовж `u` = позитивне обертання навколо `u`.
- **Інша ширина плівки / гільза:** змініть `W, ID` у `export_assets.py`, `python export_assets.py`, і число «630 мм» у `src/scene.js` (мітка розміру) та текст кроку 10 у `src/steps.js`. Значення дає `python ../v3_spindle/plan.py W ID` (S_rec).
- Рендер детермінований: у композиції немає `Math.random`, `Date.now` і мережі; 3D-дані вбудовані в `dist/scene.js`.

## Чому HyperFrames, а не Remotion

| | HyperFrames (обрано) | Remotion |
|---|---|---|
| Мова | HTML/CSS/GSAP: ШІ-агенти (Claude, Codex) пишуть її найлегше | React/TypeScript |
| Ліцензія | Apache-2.0, без плати за рендер | вільно для малих команд, далі платні місця (перевірте актуальні умови) |
| Сильна сторона | агентний CLI (`check`, `snapshot`, `render`), локально без хмари | зрілий редактор/Player, шаблони, AWS Lambda, великий розбір прикладів |
| Це відео | підходить: статична анімація з підписами + WebGL | теж підійшло б (`@remotion/three`) |

Ні той, ні інший не є класичним відеомонтажем (дорізка живого відео, колір, звук на таймлайні): для цього DaVinci Resolve / CapCut. Обидва кращі для генерованої моушн-графіки й шаблонних відео.

## Обмеження

- `npx hyperframes lint` дає попередження `nested_structure_needs_subcomposition` (підписи не винесені в під-композиції). Помилок немає; на рендер не впливає.
- Рендер програмний (SwiftShader), без GPU: ~3100 кадрів, кілька хвилин на ПК із 4+ ядрами.
- Праву сторону показано дзеркальною копією лівої (форма точна; різьба на екрані дзеркальна, це лише картинка).
- Анімація символічна: гвинти й ручки крутяться 3 оберти замість реальних ~18.
