document.addEventListener("DOMContentLoaded", function () 
{
    const leaveType = document.querySelector("[name='leave_type']");

    const fromDate = document.querySelector("[name='from_date']");
    const toDate = document.querySelector("[name='to_date']");

    const fromDateTimeDate = document.querySelector("[name='from_datetime_0']");
    const fromDateTimeTime = document.querySelector("[name='from_datetime_1']");

    const toDateTimeDate = document.querySelector("[name='to_datetime_0']");
    const toDateTimeTime = document.querySelector("[name='to_datetime_1']");


    const fromDateRow = document.querySelector(".form-row.field-from_date");
    const toDateRow = document.querySelector(".form-row.field-to_date");

    const fromDT = document.querySelector(".form-row.field-from_datetime");
    const toDT = document.querySelector(".form-row.field-to_datetime");


    function hideAll()
    {
        fromDateRow.style.display = "none";
        toDateRow.style.display = "none";
        fromDT.style.display = "none";
        toDT.style.display = "none";
    }


    function handleUI()
    {
        const type = leaveType.value;

        // ❌ No type
        if (!type)
        {
            hideAll();
            return;
        }

        // ⏱ Short / Half → only datetime
        if (type === "Short" || type === "Half")
        {
            fromDateRow.style.display = "none";
            toDateRow.style.display = "none";

            fromDT.style.display = "block";
            toDT.style.display = "block";
        }

        // 📅 Others → only date + auto time
        else
        {
            fromDateRow.style.display = "block";
            toDateRow.style.display = "block";

            fromDT.style.display = "block";
            toDT.style.display = "block";

            // ⏰ Default time
            fromDateTimeTime.value = "10:00:00";
            toDateTimeTime.value = "19:00:00";
        }
    }

    function syncfrom()
    {
        const type = leaveType.value;

        if (!type) return;

        if (type === "Casual" || type === "Sick" || type === "Earned")
        {
            if (fromDate.value)
            {
                const val = fromDate.value;

                fromDateTimeDate.value = val;
                fromDateTimeTime.value = "10:00:00";
                toDateTimeTime.value = "19:00:00";
            }
        }

        else if (type === "Short" || type === "Half")
        {
            if (fromDate.value)
            {
                const val = fromDate.value;
                fromDateTimeDate.value = val;
            }
        }
    }


    function syncto()
    {
        const type = leaveType.value;

        if (!type) return;

        if (type === "Casual" || type === "Sick" || type === "Earned")
        {
            if (toDate.value)
            {
                const val = toDate.value;

                toDateTimeDate.value = val;
                fromDateTimeTime.value = "10:00:00";
                toDateTimeTime.value = "19:00:00";
            }
        }

        else if (type === "Short" || type === "Half")
        {
            if (fromDate.value)
            {
                const val = fromDate.value;
                toDateTimeDate.value = val;
                toDate.value = val;
                autoSetLeaveDuration(); 
            }
        }
    }


    // 🎯 EVENTS
    leaveType.addEventListener("change", handleUI);

    // 🔥 RUN ON CHANGE
    fromDate.addEventListener("change", syncfrom);
    toDate.addEventListener("change", syncto);

    fromDateTimeDate.addEventListener("change", syncfrom);
    toDateTimeDate.addEventListener("change", syncto);


    setInterval(syncfrom, 300);
    setInterval(syncto, 300);


    // 🚀 INIT
    handleUI();


    
    const statusField = document.querySelector("[name='status']");
    const rejectionRow = document.querySelector(".form-row.field-rejection_reason");

    function toggleRejectionField()
    {
        if (!statusField || !rejectionRow) return;

        if (statusField.value === "Rejected")
        {
            rejectionRow.style.display = "block";
        }
        else
        {
            rejectionRow.style.display = "none";

            const rejection = document.querySelector("[name='rejection_reason']");
            rejection.value = "";
        }
    }

    statusField.addEventListener("change", toggleRejectionField);
    toggleRejectionField();



    function addHours(timeStr, hoursToAdd)
    {
        if (!timeStr) return "";

        const parts = timeStr.split(":");

        let h = parseInt(parts[0]);
        let m = parseInt(parts[1]);
        let s = parts[2] ? parseInt(parts[2]) : 0;

        let date = new Date();
        date.setHours(h, m, s);

        date.setHours(date.getHours() + hoursToAdd);

        const hh = String(date.getHours()).padStart(2, "0");
        const mm = String(date.getMinutes()).padStart(2, "0");
        const ss = String(date.getSeconds()).padStart(2, "0");

        return `${hh}:${mm}:${ss}`;
    }


    function autoSetLeaveDuration()
    {
        const type = leaveType.value;

        if (!fromDateTimeTime.value) return;

        if (type === "Short")
        {
            toDateTimeTime.value = addHours(fromDateTimeTime.value, 2);
        }

        else if (type === "Half")
        {
            toDateTimeTime.value = addHours(fromDateTimeTime.value, 4);
        }
    }
});