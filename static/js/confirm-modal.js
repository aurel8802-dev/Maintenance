document.addEventListener("DOMContentLoaded", function () {
    const modal = document.getElementById("confirmModal");
    const modalForm = document.getElementById("confirmModalForm");
    const modalName = document.getElementById("confirmModalName");

    if (!modal || !modalForm || !modalName) {
        return;
    }

    const openButtons = document.querySelectorAll(
        "[data-confirm-delete]"
    );

    const closeButtons = modal.querySelectorAll(
        "[data-confirm-close]"
    );

    function openModal(button) {
        const url = button.dataset.url;
        const name = button.dataset.name || "cet élément";

        modalForm.action = url;
        modalName.textContent = name;

        modal.classList.add("is-visible");
        modal.setAttribute("aria-hidden", "false");

        document.body.classList.add("modal-open");
    }

    function closeModal() {
        modal.classList.remove("is-visible");
        modal.setAttribute("aria-hidden", "true");

        modalForm.action = "";
        modalName.textContent = "Cet élément";

        document.body.classList.remove("modal-open");
    }

    openButtons.forEach(function (button) {
        button.addEventListener("click", function () {
            openModal(button);
        });
    });

    closeButtons.forEach(function (button) {
        button.addEventListener("click", closeModal);
    });

    document.addEventListener("keydown", function (event) {
        if (
            event.key === "Escape"
            && modal.classList.contains("is-visible")
        ) {
            closeModal();
        }
    });
});