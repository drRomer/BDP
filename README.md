# Brigada del Puente

Runner shooter de escuadrón en HTML5 Canvas (pseudo-3D). Sin anuncios ni inicio de sesión: el progreso se guarda solo en el navegador.

**Jugar:** https://drromer.github.io/BDP/

## Estructura
- `src/game.js`, `src/head.html`: juego y cabecera (CSS/HUD).
- `build_game.py`: arma `out/index.html` (aplica parches y embebe las hojas de sprites). Publicar = copiar a `docs/index.html`.
- `bake_*.py`, `bk.py`, `viewer/`: hornean modelos 3D (Tripo + Mixamo) a sprites con Chrome sin cabeza (Playwright + three.js).
- `out/sheets`, `out/props`, `out/fx`, `out/sfx`, `out/tex`: sprites, props, efectos, sonidos y texturas ya horneados (suficientes para reconstruir sin los modelos).
- `in/` (modelos originales, ~1.7 GB) no se sube.

## Reconstruir
`python3 -I build_game.py && cp out/index.html docs/index.html`
