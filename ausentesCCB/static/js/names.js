let currentIndexName = -1;
let names = [];

async function buscarNames() {
    currentIndexName = -1;  // Reset the current index
    const query = document.getElementById('name').value;
    if (query.length >= 3) {
        try {
            const response = await axios.get('/autocomplete/ausentes', {
                params: { prefix: query }
            });
            names = response.data;
            let htmlResultado = '<ul id="namesList">';
            names.forEach(name => {
                htmlResultado += `<li onclick="selecionarName('${name}')" tabindex="0" onfocus="handleFocus(this)" onblur="handleBlur(this)">${name}</li>`;
            });
            htmlResultado += '</ul>';

            document.getElementById('resultadoBuscaName').innerHTML = htmlResultado;
        } catch (error) {
            console.error('Erro ao buscar names:', error);
        }
    } else {
        document.getElementById('resultadoBuscaName').innerHTML = '';
    }
}
function handleFocus(liElement) {
    liElement.classList.add('focused');
}

function handleBlur(liElement) {
    liElement.classList.remove('focused');
}
function selecionarName(name) {
    document.getElementById('name').value = name;
    document.getElementById('resultadoBuscaName').innerHTML = '';
}

document.addEventListener("keydown", function(event) {
    const list = document.getElementById('namesList');
    if (list) {
        const items = list.getElementsByTagName('li');
        switch (event.key) {
            case "ArrowDown":
                if (currentIndexName < items.length - 1) {
                    currentIndexName++;
                    items[currentIndexName].focus();
                }
                break;
            case "ArrowUp":
                if (currentIndexName > 0) {
                    currentIndexName--;
                    items[currentIndexName].focus();
                }
                break;
            case "Enter":
                if (currentIndexName !== -1) {
                    selecionarName(items[currentIndexName].textContent);
                }
                break;
            case "Escape":
                document.getElementById('resultadoBuscaName').innerHTML = '';
                break;
        }
    }
});
