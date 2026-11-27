// État partagé de l'application (un seul objet mutable importé par tous les modules).
export const state = {
    currentEpisode: null,
    currentActIndex: 0,
    allActs: [],
    audioPlayers: {},
    currentRunName: null,
    availableRuns: [],
    speechSynthesis: null,
    currentUtterance: null,
    currentSpeechIndex: -1,
    speechPaused: false,
    episodePollingInterval: null,
    lastEpisodeHash: null,
};
