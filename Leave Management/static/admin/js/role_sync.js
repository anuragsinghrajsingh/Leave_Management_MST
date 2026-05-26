document.addEventListener("DOMContentLoaded", function ()
{
    const userRole = document.getElementById("id_role");

    if (!userRole) return;

    const employeeIdField = document.querySelector('[name$="-employee_id"]');
    const profileRoles = Array.from(document.querySelectorAll('[name$="-role"]')).filter(function (field)
    {
        return field !== userRole;
    });
    const initialRole = userRole.value;
    const initialId = employeeIdField ? employeeIdField.value : "";
    let lastHandledRole = userRole.value;
    let isSyncingRole = false;

    const initialBalanceFields = [
        document.getElementById("id_initial_sick_total"),
        document.getElementById("id_initial_earned_total"),
        document.getElementById("id_initial_unpaid"),
    ].filter(Boolean);

    function getFormRow(field)
    {
        return field.closest(".form-row") || field.closest(".form-group") || field.parentElement;
    }

    function updateInitialBalanceVisibility(roleValue)
    {
        const showInitialBalance = roleValue === "EMPLOYEE";
        const rows = new Set();

        initialBalanceFields.forEach(function (field)
        {
            field.disabled = !showInitialBalance;
            const row = getFormRow(field);
            if (row)
            {
                rows.add(row);
            }
        });

        rows.forEach(function (row)
        {
            row.style.display = showInitialBalance ? "" : "none";
        });
    }

    function syncProfileRoles(roleValue)
    {
        profileRoles.forEach(function (field)
        {
            if (field.value !== roleValue)
            {
                field.value = roleValue;
            }
        });
    }

    function syncUserRole(roleValue)
    {
        if (userRole.value !== roleValue)
        {
            userRole.value = roleValue;
        }
    }

    function updateEmployeeIdForRole(roleValue)
    {
        if (!employeeIdField || !roleValue) return;

        if (roleValue === initialRole && initialId)
        {
            employeeIdField.value = initialId;
            lastHandledRole = roleValue;
            return;
        }

        const needsUpdate = (roleValue !== lastHandledRole) || !employeeIdField.value;

        if (!needsUpdate) return;

        lastHandledRole = roleValue;

        fetch(`/api/get-next-id/${roleValue}/`)
            .then(response => response.json())
            .then(data =>
            {
                if (data.next_id)
                {
                    employeeIdField.value = data.next_id;
                }
            })
            .catch(err => console.error("Error fetching next ID:", err));
    }

    function syncRoleFromUser()
    {
        if (isSyncingRole) return;
        isSyncingRole = true;
        const roleValue = userRole.value;
        syncProfileRoles(roleValue);
        updateEmployeeIdForRole(roleValue);
        updateInitialBalanceVisibility(roleValue);
        isSyncingRole = false;
    }

    function syncRoleFromProfile(event)
    {
        if (isSyncingRole) return;
        isSyncingRole = true;
        const roleValue = event.target.value;
        syncUserRole(roleValue);
        syncProfileRoles(roleValue);
        updateEmployeeIdForRole(roleValue);
        updateInitialBalanceVisibility(roleValue);
        isSyncingRole = false;
    }

    syncRoleFromUser();
    updateInitialBalanceVisibility(userRole.value);
    userRole.addEventListener("change", syncRoleFromUser);
    profileRoles.forEach(function (field)
    {
        field.addEventListener("change", syncRoleFromProfile);
    });
});


document.addEventListener("DOMContentLoaded", function ()
{
    function attachPreview(input)
    {
        input.addEventListener("change", function ()
        {
            const file = input.files[0];
            if (!file) return;

            const reader = new FileReader();

            reader.onload = function (event)
            {
                let preview = input.parentElement.querySelector(".image-preview");

                if (!preview)
                {
                    preview = document.createElement("img");
                    preview.className = "image-preview";

                    preview.style.display = "block";
                    preview.style.marginTop = "10px";
                    preview.style.width = "120px";
                    preview.style.height = "120px";
                    preview.style.objectFit = "cover";
                    preview.style.borderRadius = "8px";
                    preview.style.border = "1px solid #ddd";

                    input.parentElement.appendChild(preview);
                }

                preview.src = event.target.result;
            };

            reader.readAsDataURL(file);
        });
    }

    const inputs = document.querySelectorAll("input[type='file']");

    inputs.forEach(input => attachPreview(input));
});
