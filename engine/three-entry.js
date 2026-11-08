// Entry of the Three.js bundle used by rm-3d.js: scenes are opened from file://, where ES modules are blocked,
// so Three.js and its glTF loader are bundled once into one classic script (vendor/three-rm.js, global THREE).
import * as T from 'three';
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js';
window.THREE = Object.assign({}, T, { GLTFLoader });
