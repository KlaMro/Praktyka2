
document.addEventListener('DOMContentLoaded', () => {
    const budgetSlider = document.getElementById('budget');
    const budgetValue = document.getElementById('budgetValue');
    const commissionValue = document.getElementById('commissionValue');
    const roiValue = document.getElementById('roiValue');
    const packageResult = document.getElementById('packageResult');
    const emailForm = document.getElementById('email-form');
    const emailInput = document.getElementById('email-input');
    const reportStatus = document.getElementById('reportStatus');
    const loader = document.getElementById('loader');
    let currentGoal = 'more_calls'; // Domyślny cel

    async function updateBudget() {
        const budget = budgetSlider.value;
        budgetValue.textContent = budget;
        try {
            const response = await fetch('/calculate_budget', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ budget: budget })
            });
            const data = await response.json();
            commissionValue.textContent = data.commission.toFixed(2);
            roiValue.textContent = data.roi.toFixed(2);
        } catch (error) {
            console.error("Błąd przy obliczaniu budżetu:", error);
            commissionValue.textContent = "Błąd";
            roiValue.textContent = "Błąd";
        }
    }

    async function selectGoal(goal) {
        currentGoal = goal;
        document.querySelectorAll('.goal-buttons button').forEach(btn => btn.classList.remove('active'));
        document.getElementById(`goal-${goal}`).classList.add('active');

        packageResult.textContent = 'Analizowanie...';
        try {
            const response = await fetch('/select_goal', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ goal: goal })
            });
            const data = await response.json();
            packageResult.textContent = data.package;
        } catch (error) {
            console.error("Błąd przy wyborze celu:", error);
            packageResult.textContent = "Błąd";
        }
    }

    async function generateReport(event) {
        event.preventDefault();
        const email = emailInput.value;
        const budget = budgetSlider.value;

        if (!email) {
            reportStatus.textContent = 'Proszę podać adres e-mail.';
            reportStatus.style.color = 'red';
            return;
        }
        
        reportStatus.textContent = '';
        loader.style.display = 'block'; // Pokaż loader

        try {
            const response = await fetch('/generate_report', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ email: email, budget: budget, goal: currentGoal })
            });
            const data = await response.json();
            reportStatus.textContent = data.message;
            reportStatus.style.color = data.message.includes("Błąd") ? 'red' : 'green';
            emailInput.value = '';
        } catch (error) {
            console.error("Błąd przy generowaniu raportu:", error);
            reportStatus.textContent = "Wystąpił nieoczekiwany błąd. Spróbuj ponownie.";
            reportStatus.style.color = 'red';
        } finally {
            loader.style.display = 'none'; // Ukryj loader
        }
    }

    // Inicjalizacja i podpięcie eventów
    budgetSlider.addEventListener('input', updateBudget);
    emailForm.addEventListener('submit', generateReport);
    document.querySelectorAll('.goal-buttons button').forEach(button => {
        button.addEventListener('click', () => selectGoal(button.id.replace('goal-','')));
    });

    // Ustawienie stanu początkowego
    updateBudget();
    selectGoal(currentGoal);
});
