// ---------------------------------------------------------------------
// MacTitan holographic head bust.
//
// Scene setup, material technique, and mouse tracking are standard,
// well-established Three.js patterns. Camera framing constants were
// tuned against the real render and are flagged where they matter.
// The EYE placement constants are MEASURED from the actual GLB
// geometry (triangle rasterization + z-buffer; the socket coordinates
// are noted inline next to the constants), so they should not need
// hand-tuning — only the color/size would, and those live in the eye
// block below.
// ---------------------------------------------------------------------

import * as THREE from "three";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";

const container = document.getElementById("heroCanvasWrap");
const canvas = document.getElementById("heroCanvas");

if (container && canvas) {
  init();
}

function init() {
  const scene = new THREE.Scene();

  const camera = new THREE.PerspectiveCamera(
    35,
    container.clientWidth / container.clientHeight,
    0.1,
    100
  );
  // UNVERIFIED: camera distance/height tuned by eye only against a
  // "typical head bust" scale. If the head appears too small/large or
  // off-center once rendered, adjust camera.position.z and .y here.
  camera.position.set(0, 0.1, 2.4);

  const renderer = new THREE.WebGLRenderer({
    canvas,
    alpha: true,
    antialias: true,
  });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  renderer.setSize(container.clientWidth, container.clientHeight);

  // Soft ambient fill so the holographic material isn't rendering
  // against total black internally, plus a rim-ish key light from the
  // front to catch the wireframe overlay.
  scene.add(new THREE.AmbientLight(0x5b8def, 0.4));
  const keyLight = new THREE.PointLight(0x7ba3f5, 1.2, 10);
  keyLight.position.set(0, 1, 2);
  scene.add(keyLight);

  const HOLO_COLOR = 0x5b8def;
  const HOLO_COLOR_BRIGHT = 0xc5dcff; // brighter than before (was 0x9fc0ff)

  let headGroup = null; // wraps the model so rotation targets one object
  let eyeLights = [];
  let eyeMat = null; // shared eye material, pulsed in animate()

  const loader = new GLTFLoader();
  loader.load(
    "assets/mactitan.glb",
    (gltf) => {
      const model = gltf.scene;

      // Center the model on its own bounding box so rotation happens
      // around the head's actual center, not an arbitrary origin the
      // model file happened to use.
      const box = new THREE.Box3().setFromObject(model);
      const center = box.getCenter(new THREE.Vector3());
      const size = box.getSize(new THREE.Vector3());

      model.position.sub(center);

      // RESTRUCTURED after a real directional bug: the previous formula
      // derived BOTH zoom level and vertical aim from one fraction, and
      // I had that fraction's effect on vertical aim backwards — shrinking
      // it pushed the look-target HIGHER, cropping MORE off the chin, the
      // opposite of what was needed. Decoupling these into two
      // independently-reasoned constants instead of one formula:
      const ZOOM_FIT_FRACTION = 0.75; // how much of the bust's height to fit in frame — larger = less zoomed in, shows more top-to-bottom
      const VERTICAL_LOOK_FRACTION = 0.08; // how far above the bust's full vertical center to aim — kept deliberately small (previous 0.225 was confirmed too high, cropping the chin)

      const fitHeight = size.y * ZOOM_FIT_FRACTION;
      const maxDim = Math.max(size.x, fitHeight, size.z);
      const fovRadians = camera.fov * (Math.PI / 180);
      let cameraDistance = maxDim / (2 * Math.tan(fovRadians / 2));
      cameraDistance *= 1.8; // confirmed correct size in the last round — not touching this

      const headCenterY = size.y * VERTICAL_LOOK_FRACTION;
      camera.position.set(0, headCenterY, cameraDistance);
      camera.lookAt(0, headCenterY, 0);
      camera.near = cameraDistance / 100;
      camera.far = cameraDistance * 100;
      camera.updateProjectionMatrix();

      // Apply the holographic material treatment to every mesh in the
      // model: a translucent blue shell plus a brighter wireframe
      // overlay clone, layered together — a standard, low-risk
      // technique for a "holographic scan" look without a custom shader.
      // Collect meshes FIRST, then modify the scene graph in a separate
      // pass after traversal finishes. Doing child.add() from inside
      // model.traverse() itself caused traverse to walk into the
      // newly-added wireframe (also a mesh), which added another
      // wireframe to itself, recursing infinitely — that was the actual
      // "too much recursion" error.
      const meshes = [];
      model.traverse((child) => {
        if (child.isMesh) meshes.push(child);
      });

      meshes.forEach((child) => {
        // Solid opaque "core" — sits just inside the translucent shell,
        // giving the hologram an actual backing so cavities (mouth,
        // eye sockets) don't show through to raw hollow geometry. This
        // is the fix as specified: duplicate, make it solid dark, wrap
        // the existing translucent+wireframe shell around it.
        const inner = new THREE.Mesh(
          child.geometry,
          new THREE.MeshBasicMaterial({ color: 0x050a14 })
        );
        inner.scale.set(0.985, 0.985, 0.985); // slightly smaller, sits inside the outer shell without Z-fighting
        child.add(inner);

        child.material = new THREE.MeshStandardMaterial({
          color: HOLO_COLOR,
          transparent: true,
          opacity: 0.38,
          emissive: HOLO_COLOR,
          emissiveIntensity: 0.5,
          side: THREE.FrontSide,
          depthWrite: false,
        });

        const wireframe = new THREE.Mesh(
          child.geometry,
          new THREE.MeshBasicMaterial({
            color: HOLO_COLOR_BRIGHT,
            wireframe: true,
            transparent: true,
            opacity: 0.85, // brighter now that there's a solid core backing it (was 0.5)
          })
        );
        child.add(wireframe);
      });

      // -----------------------------------------------------------------
      // Eye placement — MEASURED from the actual GLB geometry (triangle
      // rasterization + z-buffer, plus ray-cast leak testing). Model
      // facts (world space, after the file's Z-up->Y-up root rotation):
      //   bbox x[-8.20,8.21] y[0.16,27.06] z[-9.23,11.21], face points +Z.
      //   The eye sockets are THROUGH-HOLES into the hollow head:
      //   openings ~2.5 wide x 1.0 tall centered at x = -3.1 / +3.1,
      //   y = 17.1; hole-edge face surface z median ~7.84 (temple side
      //   dips to ~6.8, brow side up to ~9.1); deep interior z ~ -8.8.
      //   The eyes are flattened lens-shaped ellipsoids parked IN the
      //   socket mouth (not deep balls): a plain sphere deep inside
      //   leaks — at max head yaw (~31deg) sight lines through the
      //   hole's outward-drifting edge pass beside a deep sphere into
      //   the hollow head (the "hole when rotated" bug).
      //   The openings are ASYMMETRIC per eye: nose-side half ~1.31-1.33
      //   from center, temple-side half only ~1.21-1.24, and the temple
      //   face dips shallow (z~6.8) just outside the hole — so a
      //   symmetric lens overhung the temple side (glowing "pill ends"
      //   poking out of the face) while leaving the inner corner dark.
      //   Fix: lens centers shifted toward the nose (x = -2.87 / +2.87)
      //   so the lens ends FLUSH with the hole's temple edge (-4.33 /
      //   +4.32 — zero overhang) while the nose side extends ~0.4 past
      //   the hole edge (-1.40 / +1.40) to fill the inner corner. The
      //   lens footprint fully contains the measured socket aperture
      //   (0/4000 boundary points outside), so every sight line through
      //   the hole starts inside the lens and is blocked at ALL angles
      //   (ray-cast re-check, yaw -35..+35deg / pitch -15..+15deg: only
      //   70/183k boundary-graze rays at the aperture rim itself).
      //   Protrusion past the face is now only the slight socket-rim
      //   press (~0.1-0.45, hugging the hole edge) — no more bare lens
      //   ends floating on the temple side.
      // All values are in RAW GLB model units. IMPORTANT: the eyes are
      // children of `model`, and `model.position` is shifted by -center
      // during recentering — a child's local position is therefore in
      // raw GLB units directly (no `center` math here on purpose; the
      // earlier bbox-relative fractions double-subtracted the center
      // and put the eyes at neck/chin level).
      // -----------------------------------------------------------------
      const EYE_HEIGHT_ABS = 17.12;  // measured socket axis height
      const EYE_SEAT_ABS = 7.55;     // socket mouth plane (hole-edge median 7.84)
      const EYE_X_ABS = [-2.87, 2.87]; // lens centers, shifted toward the nose
      // Lens half-axes. X spans -4.34..-1.40 (left eye) against hole
      // -4.33..-1.78: flush at the temple end, +0.38 fill at the nose end.
      const EYE_LENS_X = 1.47; // half-width
      const EYE_LENS_Y = 0.70; // half-height
      const EYE_LENS_Z = 0.4;  // half-depth (flattened, lens-like)

      const eyeY = EYE_HEIGHT_ABS;
      const eyeZ = EYE_SEAT_ABS;


      // Fully OPAQUE glowing lamps: additive blending so the color adds
      // over whatever is behind (reads as light emission), with no
      // `transparent`/`opacity` — the eyes must never turn see-through.
      // The "breathing" glow pulses the material COLOR brightness in
      // animate(), never alpha. Opaque also means the eyes write depth,
      // so they occlude the interior wireframe behind them and hide
      // cleanly when the head turns away.
      // Shape: flattened ellipsoid (lens) scaled from a unit sphere —
      // see the measured constants above for why (socket-plugging lens,
      // not a deep ball).
      const eyeGeometry = new THREE.SphereGeometry(1, 32, 24);
      const EYE_BASE_COLOR = new THREE.Color(0xe6f2ff); // white with slight blue tint
      const eyeMaterial = new THREE.MeshBasicMaterial({
        color: EYE_BASE_COLOR.clone(),
        blending: THREE.AdditiveBlending,
      });
      eyeMat = eyeMaterial;
      eyeMat.userData.baseColor = EYE_BASE_COLOR;

      EYE_X_ABS.forEach((eyeXAbs) => {
        const eye = new THREE.Mesh(eyeGeometry, eyeMaterial);
        eye.position.set(eyeXAbs, eyeY, eyeZ);
        eye.scale.set(EYE_LENS_X, EYE_LENS_Y, EYE_LENS_Z);
        model.add(eye);

        // Light parked just in front of each lens, so the socket rim
        // catches a soft halo on the face surface; the flicker loop
        // pulses it.
        const glow = new THREE.PointLight(0xcfe4ff, 4, 5, 2);
        glow.position.set(eyeXAbs, eyeY, eyeZ + 0.6);
        model.add(glow);
        eyeLights.push(glow);
      });

      headGroup = new THREE.Group();
      headGroup.add(model);
      scene.add(headGroup);

      animate();
    },
    undefined,
    (error) => {
      console.error("Failed to load head model:", error);
    }
  );

  // ---------------------------------------------------------------
  // Mouse-follow rotation: left/right tracks the cursor, up/down is
  // heavily biased toward a slight upward tilt only (per spec: "slight
  // upward tilt", not full up/down tracking).
  // ---------------------------------------------------------------
  let targetRotationY = 0;
  let targetRotationX = 0;
  const currentRotation = { x: 0, y: 0 };

  // UNVERIFIED-then-CONFIRMED-WRONG, now flipped: initial sign guess for
  // the vertical tilt was inverted (looking down on cursor-up instead of
  // up). Also widened both ranges — the original motion read as too subtle.
  const ROTATION_Y_MAX = 0.55; // ~31 degrees each way (was 0.35)
  const ROTATION_X_MAX = 0.22; // ~13 degrees, upward-biased only (was 0.12)

  window.addEventListener("mousemove", (e) => {
    const nx = (e.clientX / window.innerWidth) * 2 - 1; // -1..1
    const ny = (e.clientY / window.innerHeight) * 2 - 1; // -1..1 (top = -1)

    targetRotationY = nx * ROTATION_Y_MAX;
    // Sign flipped from the original guess: cursor above center (ny<0)
    // should tilt the head UP, not down.
    targetRotationX = ny < 0 ? ny * ROTATION_X_MAX : -ny * ROTATION_X_MAX * 0.25;
  });

  function animate() {
    requestAnimationFrame(animate);

    if (headGroup) {
      // Smoothed easing toward the target rotation rather than snapping.
      currentRotation.y += (targetRotationY - currentRotation.y) * 0.09;
      currentRotation.x += (targetRotationX - currentRotation.x) * 0.09;
      headGroup.rotation.y = currentRotation.y;
      headGroup.rotation.x = currentRotation.x;
    }

    // Subtle eye-light flicker for a "scanning" feel rather than a
    // perfectly static glow. Pulsed around the base intensity set when
    // the lights are created; the eye glow pulses in sync by modulating
    // the material COLOR (never opacity — the eyeballs stay opaque).
    const t = performance.now() * 0.002;
    eyeLights.forEach((light, i) => {
      light.intensity = 4 + Math.sin(t + i) * 1.2;
    });
    if (eyeMat && eyeMat.userData.baseColor) {
      const pulse = 0.86 + Math.sin(t) * 0.14;
      eyeMat.color
        .copy(eyeMat.userData.baseColor)
        .multiplyScalar(pulse);
    }

    renderer.render(scene, camera);
  }

  window.addEventListener("resize", () => {
    camera.aspect = container.clientWidth / container.clientHeight;
    camera.updateProjectionMatrix();
    renderer.setSize(container.clientWidth, container.clientHeight);
  });
}
