# 🌳 Tree Planting Map & Survey Network Solver

This application is a real-time, field-optimised **Surveying Network Adjustment Tool** designed to run seamlessly on mobile phones and tablets. It uses a **Nonlinear Least Squares (Levenberg-Marquardt)** algorithm to convert local tree-to-tree tape measurements into precise global (X, Y) coordinates while instantly flagging measurement errors or typos in the field.

---

## 📱 Quick Field Workflow

1. **Tag the stakes:** Clearly number your tree guard stakes from `1` to `60` using tape or a sharpie.
2. **Establish your anchor:** Choose your first two trees (Tree 1 and Tree 2) in a corner. Measure the distance between them exactly. This acts as your baseline.
3. **Grow the network:** Move through the plot. For each subsequent tree, measure the distance to at least **3 surrounding trees** that have already been mapped. 
4. **Log as you go:** Input the `From`, `To`, and `Distance` values into the app sidebar on your phone. Hit **Add to Network** to save and update your live map.

---

## 🛠️ Step-by-Step Deployment (Streamlit Cloud)

### 1. Prepare Your GitHub Repository
Create a private or public repository on GitHub containing the following files:
* `app.py` (Paste the main Python script here)
* `requirements.txt` (Must contain the following text libraries):
  ```text
  numpy
  scipy
  matplotlib
  streamlit
  ```

### 2. Connect to Streamlit
1. Go to [share.streamlit.io](https://streamlit.io) and log in using your GitHub account.
2. Click **New App**, select your repository, branch, and set the main file path to `app.py`.
3. Click **Deploy**. Within 2 minutes, Streamlit will give you a live mobile web address.

---

## 🧼 Managing & Clearing Data

Because Streamlit Cloud uses an ephemeral virtual disk environment, the local file database (`survey_data.csv`) is preserved during active usage but can be intentionally reset.

### How to Completely Reset/Clear the Database for a New Survey

If you wish to clear all data or run a test run before doing your actual fieldwork, choose one of these methods:

#### Method A: The Clean Commit (Recommended for Version Control)
1. Navigate to your repository on GitHub.
2. Open the file `survey_data.csv` (if generated) or manually push a commit that deletes it.
3. If it does not exist, the app automatically boots into a blank slate containing only your initial `1,2,1.50` baseline measurement.

#### Method B: Forcing a Server Reboot via the Streamlit UI
1. Open your live app dashboard on your web browser.
2. Look at the bottom-right corner of the web interface and click the **three vertical dots (Menu)**.
3. Click **Reboot app**. 
4. This completely wipes the server's local storage disk, resets volatile cache memory, and brings the data structure back to its default baseline state.

---

## 💾 Exporting Your Finished Map

When you have finished recording measurements for all 60 trees, navigate to the **Export Survey Files** section at the very bottom of your mobile browser screen:

* **Download Raw CSV Data Ledger:** Exports the chronological log of every raw field tape measure entry you typed. Keep this as your backup survey ledger.
* **Download Calculated (X,Y) Tree Coordinates:** Exports a spreadsheet featuring structural layout rows `Tree, X_meters, Y_meters` representing the optimized coordinate values for every single tree guard.

### 🎨 Importing to Design Tools (Procreate / Concepts / Illustrator)
1. Save the generated `tree_measurement_network.png` plot image directly onto your tablet camera roll.
2. Open your preferred design program (e.g., **Procreate** or **Concepts**) and import the transparent image as your base structural layer.
3. Use the mathematically correct coordinate labels as your absolute anchor points, allowing you to paint highly detailed, artistic layout designs directly over the top on clean vector or raster layers.
