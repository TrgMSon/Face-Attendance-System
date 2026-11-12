async function loadHistory() {
    const response =
        await fetch(
            "/api/history"
        );
    const data =
        await response.json();
    const tbody =
        document.getElementById(
            "history"
        );
    tbody.innerHTML = "";
    data.forEach(row => {
        const tr =
            document.createElement(
                "tr"
            );
        tr.innerHTML = `
            <td>
                ${row.id}
            </td>
            <td>
                ${row.name}
            </td>
            <td>
                ${row.date}
            </td>
            <td>
                ${row.timestamp}
            </td>
        `;
        tbody.appendChild(tr);
    });
}

loadHistory();