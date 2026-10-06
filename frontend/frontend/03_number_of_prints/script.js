// 인화 매수는 2~4장이다.
const countEl = document.getElementById("print-count");
const minusBtn = document.querySelector('[data-action="decrease"]');
const plusBtn = document.querySelector('[data-action="increase"]');
let count = 2;

function render() {
    countEl.textContent = count;
    minusBtn.classList.toggle("disabled", count <= 2);
    plusBtn.classList.toggle("disabled", count >= 4);
}

minusBtn.addEventListener("click", (event) => {
    event.preventDefault();
    if (count > 2) count--;
    render();
});
plusBtn.addEventListener("click", (event) => {
    event.preventDefault();
    if (count < 4) count++;
    render();
});
document.getElementById("nav-next").addEventListener("click", (event) => {
    event.preventDefault();
    sessionStorage.setItem("pikcha_print_quantity", String(count));
    location.href = "../04_countdown/index.html";
});
render();
