import { state } from './state.js';

// État de la lightbox
let lightboxImages = [];

let currentLightboxIndex = -1;

// Traiter les images dans un conteneur
export function processImages(container) {
    if (!container) return;
    
    const images = container.querySelectorAll('img');
    images.forEach((img, index) => {
        // Extraire le nom du fichier depuis différents formats de chemins
        let imageFilename = null;
        const runName = state.currentRunName || '';
        
        // Priorité 1: Utiliser l'attribut src original (avant que le navigateur ne le résolve)
        // C'est le plus fiable car il contient le nom du fichier tel qu'il est dans le markdown
        const originalSrc = img.getAttribute('src');
        if (originalSrc && originalSrc.includes('../images/')) {
            // Extraire le nom du fichier depuis le chemin relatif
            imageFilename = originalSrc.split('../images/')[1].split('?')[0].split('#')[0].trim();
            // Décoder si le navigateur a déjà encodé (certains navigateurs encodent même dans l'attribut)
            if (imageFilename && imageFilename.includes('%')) {
                try {
                    // Décoder plusieurs fois si nécessaire
                    let decoded = imageFilename;
                    let previousDecoded = '';
                    let decodeCount = 0;
                    while (decoded !== previousDecoded && decodeCount < 5) {
                        previousDecoded = decoded;
                        try {
                            decoded = decodeURIComponent(decoded);
                            decodeCount++;
                        } catch (e) {
                            break;
                        }
                    }
                    imageFilename = decoded;
                } catch (e) {
                    // Si le décodage échoue, utiliser tel quel
                }
            }
        }
        // Priorité 2: Chemin relatif dans le src résolu (../images/filename.png)
        else if (img.src && img.src.includes('../images/')) {
            imageFilename = img.src.split('../images/')[1].split('?')[0].split('#')[0].trim();
        }
        // Priorité 3: Chemin résolu par le navigateur (http://localhost:8000/../images/ ou /images/)
        else if (img.src) {
            try {
                // Essayer de détecter le nom du fichier depuis différents formats
                const srcUrl = new URL(img.src, window.location.origin);
                const pathname = srcUrl.pathname;
                
                // Chercher /images/ ou /../images/ dans le chemin
                if (pathname.includes('/images/')) {
                    imageFilename = pathname.split('/images/')[1];
                } else if (pathname.includes('/../images/')) {
                    imageFilename = pathname.split('/../images/')[1];
                } else if (pathname.startsWith('/images/')) {
                    imageFilename = pathname.replace('/images/', '');
                }
                
                // Décoder le nom du fichier s'il est déjà encodé par le navigateur
                if (imageFilename) {
                    try {
                        // Décoder plusieurs fois si nécessaire (gérer les encodages multiples)
                        let decoded = imageFilename;
                        let previousDecoded = '';
                        while (decoded !== previousDecoded) {
                            previousDecoded = decoded;
                            try {
                                decoded = decodeURIComponent(decoded);
                            } catch (e) {
                                break;
                            }
                        }
                        imageFilename = decoded;
                    } catch (e) {
                        // Si le décodage échoue, utiliser tel quel
                    }
                }
            } catch (e) {
                // Si l'URL ne peut pas être parsée, ignorer
            }
        }
        
        // Si on a trouvé un nom de fichier, convertir en chemin API
        if (imageFilename) {
            // Nettoyer le nom du fichier (enlever les paramètres de requête, etc.)
            imageFilename = imageFilename.split('?')[0].split('#')[0].trim();
            
            // Décoder si déjà encodé (éviter le double encodage)
            // Décoder plusieurs fois si nécessaire
            let decoded = imageFilename;
            let previousDecoded = '';
            let decodeCount = 0;
            while (decoded !== previousDecoded && decodeCount < 3) {
                previousDecoded = decoded;
                try {
                    decoded = decodeURIComponent(decoded);
                    decodeCount++;
                } catch (e) {
                    break;
                }
            }
            imageFilename = decoded;
            
            // Maintenant encoder une seule fois pour l'URL
            const encodedFilename = encodeURIComponent(imageFilename);
            img.src = `/api/images/${encodedFilename}?run=${encodeURIComponent(runName)}`;
        } else {
            // Si on ne peut pas extraire le nom, logger un avertissement
            console.warn('Impossible d\'extraire le nom du fichier image depuis:', img.src || img.getAttribute('src'));
        }
        
        // Ajouter lazy loading
        if (!img.hasAttribute('loading')) {
            img.setAttribute('loading', 'lazy');
        }
        
        // Ajouter la classe pour le placeholder
        img.classList.add('loading');
        
        // Gérer le chargement réussi
        img.addEventListener('load', () => {
            img.classList.remove('loading');
            img.classList.add('loaded');
        });
        
        // Gérer les erreurs de chargement
        img.addEventListener('error', () => {
            img.classList.remove('loading');
            img.classList.add('error');
            console.warn('Erreur de chargement d\'image:', img.src);
        });
        
        // Ajouter le clic pour ouvrir la lightbox
        img.addEventListener('click', () => {
            openLightbox(container, index);
        });
        
        // Ajouter le style cursor pointer si pas déjà fait
        if (!img.style.cursor) {
            img.style.cursor = 'pointer';
        }
    });
}

// Ouvrir la lightbox
export function openLightbox(container, imageIndex) {
    const images = Array.from(container.querySelectorAll('img')).filter(img => !img.classList.contains('error'));
    
    if (images.length === 0) return;
    
    // Stocker les images et l'index courant
    lightboxImages = images;
    currentLightboxIndex = imageIndex >= 0 && imageIndex < images.length ? imageIndex : 0;
    
    // Afficher la lightbox
    const lightbox = document.getElementById('lightbox');
    const lightboxImage = document.getElementById('lightbox-image');
    
    if (!lightbox || !lightboxImage) return;
    
    // Charger l'image courante
    loadLightboxImage();
    
    // Afficher le modal
    lightbox.classList.add('active');
    document.body.style.overflow = 'hidden'; // Empêcher le scroll
    
    // Mettre à jour les boutons de navigation
    updateLightboxNavigation();
}

// Charger l'image dans la lightbox
export function loadLightboxImage() {
    if (currentLightboxIndex < 0 || currentLightboxIndex >= lightboxImages.length) return;
    
    const lightboxImage = document.getElementById('lightbox-image');
    const lightboxCaption = document.getElementById('lightbox-caption');
    const img = lightboxImages[currentLightboxIndex];
    
    if (!lightboxImage || !img) return;
    
    // Charger l'image
    lightboxImage.src = img.src;
    lightboxImage.alt = img.alt || '';
    
    // Afficher la légende
    if (lightboxCaption) {
        lightboxCaption.textContent = img.alt || '';
        lightboxCaption.style.display = img.alt ? 'block' : 'none';
    }
    
    // Gérer les erreurs
    lightboxImage.onerror = () => {
        if (lightboxCaption) {
            lightboxCaption.textContent = 'Erreur de chargement de l\'image';
            lightboxCaption.style.display = 'block';
        }
    };
}

// Mettre à jour les boutons de navigation
export function updateLightboxNavigation() {
    const prevBtn = document.getElementById('lightbox-prev');
    const nextBtn = document.getElementById('lightbox-next');
    
    if (prevBtn) {
        prevBtn.disabled = lightboxImages.length <= 1;
    }
    
    if (nextBtn) {
        nextBtn.disabled = lightboxImages.length <= 1;
    }
}

// Navigation dans la lightbox
export function navigateLightbox(direction) {
    if (lightboxImages.length <= 1) return;
    
    if (direction === 'prev') {
        currentLightboxIndex = (currentLightboxIndex - 1 + lightboxImages.length) % lightboxImages.length;
    } else if (direction === 'next') {
        currentLightboxIndex = (currentLightboxIndex + 1) % lightboxImages.length;
    }
    
    loadLightboxImage();
}

// Fermer la lightbox
export function closeLightbox() {
    const lightbox = document.getElementById('lightbox');
    if (lightbox) {
        lightbox.classList.remove('active');
        document.body.style.overflow = ''; // Restaurer le scroll
    }
    
    // Réinitialiser
    lightboxImages = [];
    currentLightboxIndex = -1;
}

// Initialiser la lightbox
export function initializeLightbox() {
    // Bouton fermer
    const closeBtn = document.getElementById('lightbox-close');
    if (closeBtn) {
        closeBtn.addEventListener('click', closeLightbox);
    }
    
    // Boutons navigation
    const prevBtn = document.getElementById('lightbox-prev');
    const nextBtn = document.getElementById('lightbox-next');
    
    if (prevBtn) {
        prevBtn.addEventListener('click', () => navigateLightbox('prev'));
    }
    
    if (nextBtn) {
        nextBtn.addEventListener('click', () => navigateLightbox('next'));
    }
    
    // Fermer avec ESC et navigation clavier
    document.addEventListener('keydown', (e) => {
        const lightbox = document.getElementById('lightbox');
        if (lightbox && lightbox.classList.contains('active')) {
            if (e.key === 'Escape') {
                closeLightbox();
            } else if (e.key === 'ArrowLeft') {
                navigateLightbox('prev');
            } else if (e.key === 'ArrowRight') {
                navigateLightbox('next');
            }
        }
    });
    
    // Fermer en cliquant sur le fond
    const lightbox = document.getElementById('lightbox');
    if (lightbox) {
        lightbox.addEventListener('click', (e) => {
            if (e.target === lightbox) {
                closeLightbox();
            }
        });
    }
}
