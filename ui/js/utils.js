// Échapper le HTML pour éviter les injections
// Rendu Markdown assaini : le contenu est généré par un LLM (et peut citer du web),
// il ne doit jamais être injecté dans le DOM sans DOMPurify. Sans DOMPurify -> texte échappé.
export function renderMarkdown(text) {
    const source = text || '';
    if (typeof marked === 'undefined' || typeof DOMPurify === 'undefined') {
        return source.split(/\n\n+/).map(p => `<p>${escapeHtml(p)}</p>`).join('');
    }
    return DOMPurify.sanitize(marked.parse(source), { USE_PROFILES: { html: true } });
}

export function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Extraire le nom de la source depuis une URL
export function extractSourceName(url) {
    try {
        const urlObj = new URL(url);
        let hostname = urlObj.hostname;
        
        // Retirer www. si présent
        hostname = hostname.replace(/^www\./, '');
        
        // Extraire le domaine principal
        const parts = hostname.split('.');
        if (parts.length >= 2) {
            // Prendre les deux dernières parties (ex: "mit.edu" -> "MIT", "theatlantic.com" -> "The Atlantic")
            const domain = parts.slice(-2).join('.');
            
            // Nettoyer et formater le nom
            const domainName = domain.split('.')[0];
            
            // Cas spéciaux pour les domaines connus
            const knownSources = {
                'mit': 'MIT',
                'stanford': 'Stanford',
                'harvard': 'Harvard',
                'nature': 'Nature',
                'science': 'Science',
                'wired': 'Wired',
                'theatlantic': 'The Atlantic',
                'newyorker': 'The New Yorker',
                'guardian': 'The Guardian',
                'ted': 'TED',
                'wikipedia': 'Wikipedia',
                'arxiv': 'arXiv',
                'youtube': 'YouTube',
                'github': 'GitHub',
                'medium': 'Medium',
                'substack': 'Substack',
                'nautilus': 'Nautilus',
                'aeon': 'Aeon',
                'quanta': 'Quanta Magazine',
                'technologyreview': 'MIT Technology Review',
                'lesswrong': 'LessWrong',
                'sciencedaily': 'ScienceDaily',
                'phys': 'Phys.org',
                'bbc': 'BBC',
                'pbs': 'PBS',
                'arte': 'ARTE'
            };
            
            if (knownSources[domainName.toLowerCase()]) {
                return knownSources[domainName.toLowerCase()];
            }
            
            // Capitaliser la première lettre
            return domainName.charAt(0).toUpperCase() + domainName.slice(1);
        }
        
        return hostname;
    } catch (error) {
        // Si l'URL est invalide, retourner une valeur par défaut
        return 'Source';
    }
}

// Extraire le texte brut depuis le HTML (sans les balises)
export function extractTextFromHTML(htmlElement) {
    // Créer un élément temporaire pour extraire le texte
    const temp = document.createElement('div');
    temp.innerHTML = htmlElement.innerHTML;
    
    // Récupérer tout le texte
    let text = temp.textContent || temp.innerText || '';
    
    // Nettoyer le texte : enlever les espaces multiples, sauts de ligne excessifs
    text = text.replace(/\s+/g, ' ').trim();
    
    // Améliorer la prononciation pour une meilleure qualité
    text = text.replace(/«/g, '"');
    text = text.replace(/»/g, '"');
    text = text.replace(/—/g, ' - ');
    text = text.replace(/–/g, ' - ');
    
    // Ajouter des pauses pour une meilleure compréhension
    text = text.replace(/\.\s+/g, '. '); // Espace après les points
    text = text.replace(/\?\s+/g, '? '); // Espace après les points d'interrogation
    text = text.replace(/!\s+/g, '! '); // Espace après les points d'exclamation
    
    // Améliorer la prononciation des nombres et acronymes
    text = text.replace(/(\d+)\s*km/g, '$1 kilomètres');
    text = text.replace(/(\d+)\s*m/g, '$1 mètres');
    text = text.replace(/AI/g, 'A I');
    text = text.replace(/TTS/g, 'T T S');
    
    // Ajouter des pauses après les deux-points
    text = text.replace(/:\s*/g, ': ');
    
    return text;
}
