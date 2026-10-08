// #home 오른쪽 가운데의 3D 카메라 모델 (three.js).
// · 모델: ../assets/models/camera.glb  (원본 Null.obj 를 4% 로 줄이고 meshopt 압축한 것, 재질 정보 없음 → 크림색으로 칠함)
// · 마우스 위치를 따라 천천히 기울어진다. #home 이 아닐 때는 그리지 않는다.
// · 처음 #home 에 들어왔을 때 한 번만 불러온다 (웨이팅/인화 화면에서는 로딩 안 함).

import * as THREE from "three";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";
import { MeshoptDecoder } from "three/addons/libs/meshopt_decoder.module.js";
import { RoomEnvironment } from "three/addons/environments/RoomEnvironment.js";
import { toCreasedNormals } from "three/addons/utils/BufferGeometryUtils.js";

const MODEL_URL = "../assets/models/camera.glb";
const BASE_YAW = THREE.MathUtils.degToRad(-28);   // 기본 자세: 왼쪽 앞 3/4
const BASE_PITCH = THREE.MathUtils.degToRad(14);
const FOLLOW_YAW = THREE.MathUtils.degToRad(30);  // 마우스가 화면 끝에 있을 때 더 돌아가는 각도
const FOLLOW_PITCH = THREE.MathUtils.degToRad(16);

const stage = document.querySelector(".stage");
const box = document.getElementById("camera-stage");
const isHome = () => stage.dataset.view === "home";
const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

let started = false;

function start() {
  if (started) return;
  started = true;

  let renderer;
  try {
    renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
  } catch (err) {
    console.error("WebGL 을 쓸 수 없어 3D 카메라를 띄우지 않습니다:", err);
    return;
  }
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 0.85;
  box.appendChild(renderer.domElement);

  const scene = new THREE.Scene();
  const pmrem = new THREE.PMREMGenerator(renderer);
  scene.environment = pmrem.fromScene(new RoomEnvironment(), 0.04).texture;
  scene.environmentIntensity = 0.35;             // 반사광은 약하게, 입체감은 직사광으로

  const camera = new THREE.PerspectiveCamera(28, 1, 1, 5000);
  const key = new THREE.DirectionalLight(0xfff6ea, 2.4);    // 왼쪽 위 앞에서 오는 주광
  key.position.set(-3, 4, 5);
  const rim = new THREE.DirectionalLight(0xd9e4f5, 1.2);    // 오른쪽 뒤 테두리 빛
  rim.position.set(4, 2, -3);
  scene.add(key, rim, new THREE.HemisphereLight(0xffffff, 0x24201f, 0.35));

  // 마우스 따라 도는 축(pivot) 안에 가운데 맞춘 모델을 넣는다
  const pivot = new THREE.Group();
  pivot.rotation.set(BASE_PITCH, BASE_YAW, 0);
  scene.add(pivot);

  const material = new THREE.MeshStandardMaterial({ color: 0xf8f5ef, roughness: 0.55, metalness: 0.05 });
  let radius = 1;

  const loader = new GLTFLoader();
  loader.setMeshoptDecoder(MeshoptDecoder);
  loader.load(MODEL_URL, (gltf) => {
    const model = gltf.scene;
    model.traverse((obj) => {
      if (!obj.isMesh) return;
      obj.geometry = toCreasedNormals(obj.geometry, Math.PI / 6);   // 원본에 법선이 없어서 30° 기준으로 만든다
      obj.material = material;
    });
    const bounds = new THREE.Box3().setFromObject(model);
    model.position.sub(bounds.getCenter(new THREE.Vector3()));
    radius = bounds.getSize(new THREE.Vector3()).length() / 2;
    pivot.add(model);
    resize();
    box.classList.add("is-ready");
  }, undefined, (err) => console.error("3D 카메라 모델을 불러오지 못했습니다:", err));

  // 화면에 보이는 실제 크기에 맞춰 그린다 (무대가 --fit 배로 확대/축소되므로 getBoundingClientRect 사용)
  function resize() {
    const r = box.getBoundingClientRect();
    if (!r.width || !r.height) return;
    renderer.setSize(r.width, r.height, false);
    camera.aspect = r.width / r.height;
    // 모델이 영역 폭의 약 60% 를 차지하도록 거리 조절
    const fitH = radius / Math.tan(THREE.MathUtils.degToRad(camera.fov / 2));
    const fitW = fitH / camera.aspect;
    camera.position.set(0, 0, Math.max(fitH, fitW) * 1.5);
    camera.near = camera.position.z / 100;
    camera.far = camera.position.z * 10;
    camera.updateProjectionMatrix();
  }
  window.addEventListener("resize", resize);

  // 마우스 위치(-1 ~ 1) → 목표 각도. 매 프레임 조금씩 따라간다
  const target = { x: 0, y: 0 };
  window.addEventListener("pointermove", (event) => {
    const r = box.getBoundingClientRect();
    target.x = THREE.MathUtils.clamp((event.clientX - (r.left + r.width / 2)) / (window.innerWidth / 2), -1, 1);
    target.y = THREE.MathUtils.clamp((event.clientY - (r.top + r.height / 2)) / (window.innerHeight / 2), -1, 1);
  });
  document.addEventListener("pointerleave", () => { target.x = 0; target.y = 0; });

  const clock = new THREE.Clock();
  renderer.setAnimationLoop(() => {
    if (!isHome()) return;                       // 다른 화면에서는 쉬기
    const t = clock.getElapsedTime();
    const ease = 0.06;
    pivot.rotation.y += (BASE_YAW + target.x * FOLLOW_YAW - pivot.rotation.y) * ease;
    pivot.rotation.x += (BASE_PITCH + target.y * FOLLOW_PITCH - pivot.rotation.x) * ease;
    pivot.position.y = reduceMotion ? 0 : Math.sin(t * 1.2) * radius * 0.03;   // 살짝 떠 있는 느낌
    renderer.render(scene, camera);
  });
}

function check() {
  if (isHome()) {
    start();
    window.dispatchEvent(new Event("resize"));   // 숨겨져 있다가 보이면 크기 다시 계산
  }
}
window.addEventListener("hashchange", () => requestAnimationFrame(check));
check();
