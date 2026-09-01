document.addEventListener("DOMContentLoaded", function () {
    const form = document.querySelector("[data-filters-form]");

    if (!form) {
        return;
    }

    const storageKey = form.dataset.storageKey;

    if (!storageKey) {
        return;
    }

    const fields = form.querySelectorAll(
        "input[name], select[name]"
    );

    const savedFilters = JSON.parse(
        localStorage.getItem(storageKey) || "{}"
    );

    const currentParams = new URLSearchParams(
        window.location.search
    );

    let filtersRestored = false;

    /*
     * Restauration des filtres uniquement si la page
     * est ouverte sans paramètres dans l'URL.
     */
    if (currentParams.toString() === "") {
        fields.forEach(function (field) {
            const savedValue = savedFilters[field.name];

            if (savedValue !== undefined) {
                field.value = savedValue;

                if (savedValue !== "") {
                    filtersRestored = true;
                }
            }
        });
    }

    function saveFilters() {
        const filters = {};

        fields.forEach(function (field) {
            filters[field.name] = field.value;
        });

        localStorage.setItem(
            storageKey,
            JSON.stringify(filters)
        );
    }

    function submitFilters() {
        saveFilters();
        form.submit();
    }

    /*
     * Recharge la page avec les filtres restaurés.
     */
    if (filtersRestored) {
        submitFilters();
        return;
    }

    /*
     * Les listes déroulantes appliquent immédiatement le filtre.
     */
    fields.forEach(function (field) {
        if (field.tagName === "SELECT") {
            field.addEventListener("change", submitFilters);
        }
    });

    /*
     * La recherche attend 500 ms après la dernière lettre saisie.
     */
    const searchInput = form.querySelector(
        'input[name="recherche"]'
    );

    let searchTimer;

    if (searchInput) {
        searchInput.addEventListener("input", function () {
            clearTimeout(searchTimer);

            searchTimer = setTimeout(function () {
                submitFilters();
            }, 500);
        });
    }

    /*
     * Sauvegarde également lors d'un envoi manuel.
     */
    form.addEventListener("submit", saveFilters);

    /*
     * Efface les filtres mémorisés.
     */
    const resetButton = form.querySelector(
        "[data-reset-filters]"
    );

    if (resetButton) {
        resetButton.addEventListener("click", function () {
            localStorage.removeItem(storageKey);
        });
    }
});