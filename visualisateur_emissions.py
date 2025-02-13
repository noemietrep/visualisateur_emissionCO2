#################################################
#  Émile Lefort <EmileLef>
#  Noémie Trépanier <noemietrep>
#################################################

import sys
import sqlite3

import numpy as np
import pandas as pd
from PySide6.QtGui import QAction, QColorConstants, QPainter, QPixmap
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QVBoxLayout, QWidget,
    QFileDialog, QMessageBox, QCheckBox, QComboBox,
    QPushButton, QGridLayout, QLabel, QRadioButton, QButtonGroup, QHBoxLayout
)
from matplotlib.backends.backend_qt import NavigationToolbar2QT
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure


# Fenêtre principale
class FenetrePrincipale(QMainWindow):
    def __init__(self):
        super().__init__()
        self.series_info = None
        self.serie_type = None
        self.info = None
        self.con_bd = None
        self.bouton_descendant = None
        self.bouton_ligne = None
        self.bouton_barre = None
        self.bouton_ascendant = None
        self.df_filtre = None
        self.entite_choisie = None
        self.axe_y = None
        self.axe_x = None
        self.emissions_bd = None
        self.df = None
        self.entites = None
        self.case_tri = None
        self.statistique = {"NombreDonnees": 0, "MoyenneEmission": 0, "EcartType": 0, "Maximum": 0, "Minimum": 0}
        self.setWindowTitle("Graphique")
        self.resize(900, 700)

        # Configuration de la zone centrale
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)

        self.main_layout = QVBoxLayout()
        self.central_widget.setLayout(self.main_layout)

        # Initialiser la figure Matplotlib
        self.figure = Figure()
        self.canvas = FigureCanvas(self.figure)
        self.main_layout.addWidget(self.canvas)

        # Ajouter une barre de navigation pour Matplotlib
        self.toolbar = NavigationToolbar2QT(self.canvas, self)
        self.main_layout.addWidget(self.toolbar)

        # Création des menus
        self.creer_menu()

        # Ajout d'un grid layout pour les options du graphique
        self.grid_layout = QGridLayout()
        self.main_layout.addLayout(self.grid_layout)

        # Création de la liste déroulante des entités
        self.creer_liste_entites()

        # Ajouter la liste déroulante pour les types de graphique
        self.type_graphique = QLabel('Type de graphique:')
        self.grid_layout.addWidget(self.type_graphique, 1, 0, 1, 1)
        self.creer_types_graphiques()

        # Création de la case tri
        self.creer_case()

        # Bouton pour exporter en PDF
        self.export_button = QPushButton("Exporter")
        self.export_button.clicked.connect(self.exporter)
        self.main_layout.addWidget(self.export_button)

        # Ajouter la liste déroulante pour les types de tri
        self.creer_types_tri()

        self.importer_par_defaut(fichier_csv="co-emissions-per-capita new.csv")

    # Créer la base de données à partir du fichier CSV par défaut
    def importer_par_defaut(self, fichier_csv):
        try:
            self.df = pd.read_csv(fichier_csv)
            self.df.rename(
                columns={"Entity": "Entite", "Year": "Annee", "Annual CO₂ emissions (per capita)": "Co2"},
                inplace=True
            )
            self.df["Co2"] = pd.to_numeric(self.df["Co2"], errors="coerce")
            self.df = self.df.dropna(subset=["Co2"]) # Enlever les not a number
            self.df = self.df[self.df["Co2"] > 0]    # Garder seulement les chiffres plus grands que 0
            self.df = self.df.astype({"Entite": str, "Annee": int})

            self.creer_bd()
            self.liste_entites()  # Charger les entités après création
            self.donnees_graph()  # Udapter les données du graphique
            self.update_info()    # Updater les infos de la BD
        # Gérer l'exception
        except Exception as e:
            QMessageBox.critical(self, "Erreur", f"Une erreur est survenue lors de l'importation : {e}")

    # Créer la liste déroulante
    def creer_liste_entites(self):
        self.entites = QComboBox()
        nom = QLabel("Entité sélectionnée:")
        layout = QHBoxLayout()
        layout.addWidget(nom)
        layout.addWidget(self.entites)
        self.grid_layout.addLayout(layout, 0, 0, 1, 1)
        self.entites.currentTextChanged.connect(self.donnees_graph)
        self.entites.currentTextChanged.connect(self.statistiques)

    # Méthode pour remplir la liste
    def liste_entites(self):
        self.entites.clear()
        entite_distincte = self.emissions_bd.entite_distincte()
        self.entites.addItems(entite_distincte)

    # Faire les boutons pour choisir le type de graphique
    def creer_types_graphiques(self):
        self.bouton_barre = QRadioButton("Barres") # Dans un QRadioButton pour l'auto-exclusivité
        self.bouton_barre.setChecked(True)
        self.bouton_barre.toggled.connect(self.donnees_graph)
        self.bouton_ligne = QRadioButton("Lignes")
        self.bouton_ligne.toggled.connect(self.donnees_graph)
        groupe_boutons = QButtonGroup()
        groupe_boutons.addButton(self.bouton_barre)
        groupe_boutons.addButton(self.bouton_ligne)
        widget_groupe = QWidget()
        layout = QVBoxLayout()
        widget_groupe.setLayout(layout)
        layout.addWidget(self.bouton_barre)
        layout.addWidget(self.bouton_ligne)
        self.grid_layout.addWidget(widget_groupe, 2, 0, 2, 1)

    # Créer la case tri
    def creer_case(self):
        self.case_tri = QCheckBox("Tri:")
        self.case_tri.setChecked(False)
        self.case_tri.stateChanged.connect(self.afficher_liste_tris)
        self.grid_layout.addWidget(self.case_tri, 1, 1, 1, 1)

    # Créer les boutons pour choisir le type de tri
    def creer_types_tri(self):
        self.bouton_ascendant = QRadioButton("Ascendant") # Dans un QRadioButton pour l'auto-exclusivité
        self.bouton_ascendant.setChecked(True)
        self.bouton_ascendant.setEnabled(False)
        self.bouton_ascendant.clicked.connect(self.donnees_graph)
        self.bouton_descendant = QRadioButton("Descendant")
        self.bouton_descendant.setEnabled(False)
        self.bouton_descendant.clicked.connect(self.donnees_graph)
        groupe_boutons = QButtonGroup()
        groupe_boutons.addButton(self.bouton_ascendant)
        groupe_boutons.addButton(self.bouton_descendant)
        widget_groupe = QWidget()
        layout = QVBoxLayout()
        widget_groupe.setLayout(layout)
        layout.addWidget(self.bouton_ascendant)
        layout.addWidget(self.bouton_descendant)
        self.grid_layout.addWidget(widget_groupe, 2, 1, 1, 1)

    # Donner accès au tri seulement si la case est cochée
    def afficher_liste_tris(self):
        if self.case_tri.isChecked():
            try:
                self.bouton_ascendant.setEnabled(True)
                self.bouton_descendant.setEnabled(True)
                self.donnees_graph()
            except NameError:
                QMessageBox.information(
                    self,
                    "Erreur d'importation",
                    "Vous devez importer un fichier avant de trier")
                self.case_tri.setChecked(False)
                self.bouton_ascendant.setEnabled(False)
                self.bouton_descendant.setEnabled(False)
        else:
            self.bouton_ascendant.setEnabled(False)
            self.bouton_descendant.setEnabled(False)
            self.donnees_graph()

    # Créer le menu de la fenêtre avec ses actions
    def creer_menu(self):
        menu_bar = self.menuBar()

        # Menu "Fichier"
        fichier_menu = menu_bar.addMenu("Fichier")

        # Action "Importer"
        importer_action = QAction("Importer", self)
        importer_action.triggered.connect(self.importer_fichier)
        fichier_menu.addAction(importer_action)

        # Action "Quitter"
        quitter_action = QAction("Quitter", self)
        quitter_action.setShortcut("Ctrl+Q")
        quitter_action.triggered.connect(self.close)
        fichier_menu.addAction(quitter_action)

        # Menu "Aide"
        aide_menu = menu_bar.addMenu("Aide")

        # Action "À propos"
        a_propos = QAction("À propos", self)
        a_propos.triggered.connect(self.afficher_a_propos)
        aide_menu.addAction(a_propos)

        infos_donnees = QAction("Infos données", self)
        infos_donnees.triggered.connect(self.afficher_infos)
        aide_menu.addAction(infos_donnees)

    # Ajouter le file directory
    def importer_fichier(self):
        #Ouvrir le FileDiaolog
        chemin_fichier, _ = QFileDialog.getOpenFileName(self, "Importer un fichier",
                                                        " ./tp3-visualisateur-d-missions-co2-meteo_noemie_emile_3",
                                                        "*.csv")
        if chemin_fichier:
            try:
                self.df = pd.read_csv(chemin_fichier)  #Importer les données dans un DataFrame Pandas
                self.df.rename(
                    columns={"Entity": "Entite",  # Renommer les Séries
                             "Year": "Annee",
                             "Annual CO₂ emissions (per capita)": "Co2"},
                    inplace=True)
                self.df["Co2"] = pd.to_numeric(self.df["Co2"],
                                               errors="coerce")  #Transformer la colonne d'émissions en numérique
                self.df = self.df.dropna(subset=["Co2"])  #Enlever les Not a Number
                self.df = self.df[self.df["Co2"] > 0]  # Filtrer les chiffres plus grands que 0
                self.df = self.df.astype({
                    "Entite": str,  # Modifier le type de Séries
                    "Annee": int,
                })

                self.creer_bd()  # Créer la BD SQLite
                self.liste_entites()  # Afficher la liste déroulante des entités
                self.donnees_graph()  # Udapter les données du graphique
                self.update_info()

            except UnicodeDecodeError:  #Gérer les exceptions
                QMessageBox.information(
                    self,
                    "Erreur d'importation",
                    "Le fichier ne peut être importé")

    def afficher_a_propos(self):
        QMessageBox.information(
            self,
            "À propos",
            "Visualisateur d'émissions\nDéveloppé par Noémie Trépanier et Émile Lefort"
        )

    def afficher_infos(self):
        if self.info is None:
            QMessageBox.information(
                self,
                "Info données",
                "Il n'y a pas de donnée à recueillir."
            )
        else:
            QMessageBox.information(
                self,
                "Info données",
                f"Le fichier contient {self.info["DonneesTot"]} données et il y a {self.info["EntiteUnique"]} entités uniques.\n"
                f"Voici les séries contenues:\n{self.series_info}"
            )

    # Recueillir les informations pour l'action "Info données"
    def update_info(self):
        self.info = {"DonneesTot": self.emissions_bd.nb_donnees_tot(),
                     "EntiteUnique": self.emissions_bd.nb_entite()}
        self.serie_type = {}
        liste = self.df.dtypes
        for serie, types in liste.items():
            self.serie_type[serie] = types
        self.series_info = "\n".join([f"{serie}: {types}" for serie, types in self.serie_type.items()])

    # Trier les données pour chaque axe selon le tri en question
    def tri_ascendant(self):
        self.df_filtre = self.df_filtre.sort_values("Co2", ascending=True)
        self.axe_x = self.df_filtre["Annee"].tolist()
        self.axe_y = self.df_filtre["Co2"].tolist()

    def tri_descendant(self):
        self.df_filtre = self.df_filtre.sort_values("Co2", ascending=False)
        self.axe_x = self.df_filtre["Annee"].tolist()
        self.axe_y = self.df_filtre["Co2"].tolist()

    # Aller chercher les statistiques et les updates dans le menu
    def statistiques(self):
        try:
            emission = self.df_filtre["Co2"]

            # Vérifiez que la colonne "Co2" n'est pas vide
            if emission.empty:
                raise ValueError("La colonne 'Co2' est vide, impossible de calculer les statistiques.")

            # Remplir le dictionnaire avec les bonnes informations
            self.statistique["NombreDonnees"] = emission.count()
            self.statistique["MoyenneEmission"] = (emission.sum() / self.statistique["NombreDonnees"]).round(2)
            self.statistique["EcartType"] = emission.std().round(2)
            self.statistique["Maximum"] = emission.max()
            self.statistique["Minimum"] = emission.min()
            self.afficher_stats()

        except KeyError as e:
            QMessageBox.critical(self, "Erreur",
                                 f"Erreur : la colonne spécifiée est absente du DataFrame. Détail : {e}")
        except AttributeError as e:
            QMessageBox.critical(self, "Erreur", f"Erreur : une erreur liée aux attributs est survenue. Détail : {e}")
        except ValueError as e:
            QMessageBox.critical(self, "Erreur", f"Erreur : {e}")
        except Exception as e:
            QMessageBox.critical(self, "Erreur", f"Une erreur inattendue est survenue : {e}")

    # Afficher les statistiques dans le canevas
    def afficher_stats(self):
        etiquette = QLabel()
        canevas = QPixmap(400, 150)  # Création du canevas avec 400 pixels de largeur et 150 de hauteur
        canevas.fill(QColorConstants.LightGray)  # Remplir le canevas d'une couleur
        painter = QPainter(canevas)  # Dessiner le texte
        painter.drawText(10, 20, f"{self.entite_choisie} contient {self.statistique["NombreDonnees"]} données.")
        painter.drawText(10, 50, f"La moyenne de ses émissions de Co2 est de {self.statistique["MoyenneEmission"]}.")
        painter.drawText(10, 80, f"L'écart-type de ses émissions de Co2 est de {self.statistique["EcartType"]}.")
        painter.drawText(10, 110, f"Le maximum de ses émissions de Co2 est {self.statistique["Maximum"]}.")
        painter.drawText(10, 140, f"Le minimum de ses émissions de Co2 est {self.statistique["Minimum"]}.")
        painter.end()
        etiquette.setPixmap(canevas)  # Mettre le canevas sur un widget pour l'ajouter au layout
        self.grid_layout.addWidget(etiquette, 1, 2, 2, 1)

    # Création du graphique en fonction de l'entité et du format choisi
    def donnees_graph(self):
        self.entite_choisie = self.entites.currentText()
        self.df_filtre = self.df[self.df["Entite"] == self.entite_choisie]
        if self.case_tri.isChecked():
            if self.bouton_ascendant.isChecked():
                self.tri_ascendant()
            else:
                self.tri_descendant()
        if not self.case_tri.isChecked():
            self.axe_x = self.emissions_bd.annee_entite(self.entite_choisie)
            self.axe_y = self.emissions_bd.emission_entite(self.entite_choisie)
        if self.bouton_barre.isChecked():
            self.afficher_barres()
        elif self.bouton_ligne.isChecked():
            self.afficher_lignes()

    # Affiche un graphique de type 'Barres'
    def afficher_barres(self):
        self.figure.clear()
        ax = self.figure.add_subplot(111)
        ax.bar(np.arange(len(self.axe_x)), self.axe_y, color="blue")
        ax.set_xticks(range(len(self.axe_x)))
        ax.set_xticklabels(self.axe_x)
        ax.set_title(f"Émissions de Co2 de {self.entite_choisie} selon les années")
        ax.set_ylabel("Émissions")
        ax.set_xlabel("Années")
        self.canvas.draw()

    # Affiche un graphique de type 'Lignes'
    def afficher_lignes(self):
        self.figure.clear()
        ax = self.figure.add_subplot(111)
        ax.plot(np.arange(len(self.axe_x)), self.axe_y, marker="o", linestyle="-", color="red")
        ax.set_xticks(range(len(self.axe_x)))
        ax.set_xticklabels(self.axe_x)
        ax.set_title(f"Émissions de Co2 de {self.entite_choisie} selon les années")
        ax.set_ylabel("Émissions")
        ax.set_xlabel("Années")
        self.canvas.draw()

    # Ouvre ou crée (si inexistante) une connection sur une BD SQLite
    def creer_bd(self):
        self.emissions_bd = EmissionsBD()
        self.con_bd = EmissionsBD().con
        # Transfert des données du DataFrame Panda dans la base de données SQL
        self.emissions_bd.creer_table(self.df)

    # Exporte le fichier en PDF
    def exporter(self):
        chemin_fichier, _ = QFileDialog.getSaveFileName(self, "Exporter le graphique", "", "*.pdf")
        if chemin_fichier:
            try:
                self.figure.savefig(chemin_fichier, format='pdf')
                QMessageBox.information(self, "Succès", "Graphique exporté avec succès en PDF.")
            except Exception as e:
                QMessageBox.critical(self, "Erreur", f"Une erreur est survenue lors de l'exportation : {e}")

# Classe de la BD SQLi
class EmissionsBD:

    def __init__(self):
        # Ouvre une connection sur une BD contenue dans un fichier emissions.db ou la créée si inexistante
        self.con = sqlite3.connect("emissions.db")

    # Requête pour créer la table
    def creer_table(self, dataframe):
        curseur = self.con.cursor()
        curseur.execute("CREATE TABLE IF NOT EXISTS Emission(Entite, Annee, Co2)")
        dataframe.to_sql("Emission", self.con, if_exists="replace", index=False)  # L'écrase si elle existe déjà
        self.con.commit()

    # Requête pour sélectionner les entités sans doublon
    def entite_distincte(self):
        curseur = self.con.cursor()
        curseur.execute("SELECT DISTINCT Entite FROM Emission ORDER BY Entite ASC")
        entite_distinctes = [element[0] for element in curseur.fetchall()]
        curseur.close()
        return entite_distinctes

    # Requête pour sélectionner les années de l'entité en question
    def annee_entite(self, entite):
        curseur = self.con.cursor()
        curseur.execute("SELECT Annee FROM Emission WHERE Entite = ?", (entite,))
        annees = [element[0] for element in curseur.fetchall()]
        curseur.close()
        return annees

    # Requête pour sélectionner les émissions de Co2 de l'entité en question
    def emission_entite(self, entite):
        curseur = self.con.cursor()
        curseur.execute("SELECT Co2 FROM Emission WHERE Entite = ?", (entite,))
        co2 = [element[0] for element in curseur.fetchall()]
        curseur.close()
        return co2

    # Requête pour compter le nombre de données total
    def nb_donnees_tot(self):
        curseur = self.con.cursor()
        curseur.execute("SELECT Co2 FROM Emission")
        donnees_tot = [element[0] for element in curseur.fetchall()]
        nombre = len(donnees_tot)
        curseur.close()
        return nombre

    # Requête pour compter le nombre d'entités uniques
    def nb_entite(self):
        curseur = self.con.cursor()
        curseur.execute("SELECT DISTINCT Entite FROM Emission ORDER BY Entite ASC")
        entite_distinctes = [element[0] for element in curseur.fetchall()]
        nombre = len(entite_distinctes)
        curseur.close()
        return nombre


if __name__ == "__main__":
    app = QApplication(sys.argv)
    fenetre = FenetrePrincipale()
    fenetre.show()
    sys.exit(app.exec())
