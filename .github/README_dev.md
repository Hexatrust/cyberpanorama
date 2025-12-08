# 🤖 Système d'Automatisation GitHub

## Vue d'ensemble

Ce dossier contient le système d'automatisation complet pour le radar Hexatrust, permettant l'ajout automatique d'entreprises via des GitHub Issues.

## 📁 Structure

```
.github/
├── ISSUE_TEMPLATE/
│   └── add_company.yml          # Formulaire d'ajout d'entreprise
├── workflows/
│   ├── process-new-company.yml  # Traitement des nouvelles entreprises
│   └── regenerate-radar.yml     # Régénération automatique du radar
└── scripts/
    └── parse_issue.py           # Parser d'issues GitHub
```

---

## 🎯 Fonctionnement

### 1. 📝 Soumission d'une Entreprise

**Utilisateur** → Remplit le formulaire GitHub Issue → **Issue créée**

Le formulaire (`ISSUE_TEMPLATE/add_company.yml`) collecte :
- Nom de l'entreprise
- Fonction NIST
- Taille
- Description
- URL du logo
- Critères de souveraineté

### 2. 🔍 Validation Manuelle

**Mainteneur** → Examine l'issue → Ajoute le label `approved`

Critères de validation :
- ✅ Entreprise française/européenne
- ✅ Critères de souveraineté respectés
- ✅ Logo accessible et de qualité
- ✅ Informations complètes et vérifiabl

### 3. 🤖 Traitement Automatique

**GitHub Actions** → Détecte le label `approved` → Lance le workflow

Étapes du workflow (`process-new-company.yml`) :

1. **Checkout** : Clone le repository
2. **Setup Python** : Installe Python 3.11
3. **Install system deps** : Installe libcairo2, libjpeg, libpng, etc.
4. **Install Python deps** : Installe les dépendances Python
5. **Parse issue** : Extrait les données de l'issue
   - Script `parse_issue.py` analyse le corps de l'issue
   - Télécharge le logo depuis l'URL fournie
   - Ajoute l'entreprise au fichier Excel
6. **Generate radar** : Exécute `src/main.py`
   - Régénère le radar SVG
   - Régénère le radar PNG
7. **Commit** : Commit automatique des changements
8. **Push** : Push vers la branche principale
9. **Comment** : Ajoute un commentaire sur l'issue
10. **Close** : Ferme l'issue avec le label `completed`

### 4. 📢 Notification

**GitHub** → Notifie l'utilisateur → **Issue fermée avec succès**

---

## 🔄 Régénération Automatique

Le workflow `regenerate-radar.yml` régénère automatiquement le radar :

### Triggers

1. **Manuel** : Via l'onglet Actions
2. **Programmé** : Tous les jours à 2h du matin (UTC)
3. **Automatique** : Sur push vers `main` qui modifie :
   - `assets/solutions.xlsx`
   - `assets/logos/**`

### Processus

```
Trigger → Setup → Generate Radar → Check Changes → Commit (si changements) → Push
```

---

## 🛠️ Configuration Requise

### Permissions GitHub Actions

Dans les settings du repository, activez :

**Settings → Actions → General → Workflow permissions**
- ✅ Read and write permissions
- ✅ Allow GitHub Actions to create and approve pull requests

### Secrets

Aucun secret supplémentaire requis. Le workflow utilise :
- `GITHUB_TOKEN` (fourni automatiquement)

---

## 📝 Scripts

### `parse_issue.py`

**Rôle :** Parse une GitHub Issue et ajoute l'entreprise au radar

**Utilisation :**
```bash
python3 .github/scripts/parse_issue.py <issue_number>
```

**Variables d'environnement requises :**
- `GITHUB_TOKEN` : Token d'authentification GitHub
- `GITHUB_REPOSITORY` : Nom du repository (format: owner/repo)

**Sorties (pour GitHub Actions) :**
- `company_name` : Nom de l'entreprise
- `fonction_nist` : Fonction NIST
- `taille` : Taille de l'entreprise

**Processus :**
1. Récupère l'issue via l'API GitHub
2. Parse le corps de l'issue avec regex
3. Télécharge le logo depuis l'URL
4. Ajoute l'entreprise directement au fichier Excel (pandas/openpyxl)
5. Exporte les variables pour GitHub Actions

---

## 🔧 Maintenance

### Ajouter un Nouveau Champ

1. **Modifier le formulaire** : `.github/ISSUE_TEMPLATE/add_company.yml`
   ```yaml
   - type: input
     id: nouveau_champ
     attributes:
       label: Mon nouveau champ
   ```

2. **Modifier le parser** : `.github/scripts/parse_issue.py`
   ```python
   patterns = {
       'nouveau_champ': r'### Mon nouveau champ\s*\n\s*(.+)',
       # ...
   }
   ```

3. **Utiliser dans le workflow** : `.github/workflows/process-new-company.yml`
   ```yaml
   - name: Use new field
     run: |
       echo "New field: ${{ steps.parse_issue.outputs.nouveau_champ }}"
   ```

### Tester Localement

```bash
# Définir les variables d'environnement
export GITHUB_TOKEN="your_token"
export GITHUB_REPOSITORY="owner/repo"

# Tester le parser
python3 .github/scripts/parse_issue.py 123

# Tester la génération du radar
python3 src/main.py
```

### Déboguer un Workflow

1. **Activer les logs de debug** :
   ```yaml
   env:
     ACTIONS_STEP_DEBUG: true
     ACTIONS_RUNNER_DEBUG: true
   ```

2. **Voir les logs** :
   - Onglet Actions du repository
   - Cliquer sur le workflow failed
   - Examiner chaque étape

3. **Tester manuellement** :
   ```bash
   # Dans l'onglet Actions
   # Sélectionner le workflow
   # Cliquer sur "Run workflow"
   ```

---

## 📊 Statistiques

### Workflows Actifs

| Workflow | Trigger | Fréquence | Durée moyenne |
|----------|---------|-----------|---------------|
| `process-new-company.yml` | Label `approved` | À la demande | ~2-3 min |
| `regenerate-radar.yml` | Programmé | Quotidien (2h UTC) | ~1-2 min |
| `regenerate-radar.yml` | Push main | Sur changement | ~1-2 min |

### Limites GitHub Actions

- **Minutes gratuites/mois** : 2,000 (public repo: illimité)
- **Stockage** : 500 MB
- **Durée max d'un job** : 6 heures
- **Durée max d'un workflow** : 72 heures

---

## 🚨 Résolution de Problèmes

### Erreur : "Permission denied"

**Cause :** Permissions insuffisantes pour GitHub Actions

**Solution :**
1. Settings → Actions → General
2. Workflow permissions → "Read and write permissions"

### Erreur : "Module not found"

**Cause :** Dépendances non installées

**Solution :** Vérifier `requirements.txt` et l'étape d'installation

### Erreur : "Logo download failed"

**Cause :** URL du logo inaccessible

**Solutions possibles :**
1. Vérifier que l'URL est publique
2. Vérifier le format du fichier
3. Tester l'URL manuellement : `curl -I <url>`

### Erreur : "Excel file locked"

**Cause :** Conflit de versions du fichier Excel

**Solution :** Pull les dernières modifications avant le workflow

---

## 🔐 Sécurité

### Validation des Entrées

- ✅ Validation des fonctions NIST
- ✅ Validation des tailles (1-3)
- ✅ Sanitization des noms de fichiers
- ✅ Limite de taille des logos (timeout 30s)
- ✅ Vérification des extensions de fichiers

### Authentification

- ✅ Utilisation de `GITHUB_TOKEN` (scope limité)
- ✅ Pas de secrets sensibles dans les workflows
- ✅ Validation manuelle (label `approved`) requise

### Bonnes Pratiques

- ✅ Pas d'exécution de code arbitraire
- ✅ Checkout en lecture seule par défaut
- ✅ Commit avec bot account
- ✅ Validation des URLs avant téléchargement

---

## 📚 Ressources

- [GitHub Actions Documentation](https://docs.github.com/en/actions)
- [GitHub Issue Forms](https://docs.github.com/en/communities/using-templates-to-encourage-useful-issues-and-pull-requests/syntax-for-issue-forms)
- [GitHub REST API](https://docs.github.com/en/rest)

---

## 🆘 Support

Pour toute question sur les workflows :

1. Consultez les logs dans l'onglet Actions
2. Testez manuellement avec `parse_issue.py`
3. Créez une issue avec le label `workflow:bug`

---

**Version** : 2.0
**Dernière mise à jour** : 2025-11-05
