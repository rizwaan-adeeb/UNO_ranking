import streamlit as st
import trueskill
import json
from pathlib import Path
import pandas as pd
from PIL import Image
from datetime import datetime

# Initialize TrueSkill environment
env = trueskill.TrueSkill(draw_probability=0.0)

# Load the UNO logo
try:
    uno_logo = Image.open("UNO_image.png")
    logo_loaded = True
except Exception as e:
    logo_loaded = False
    print(f"Error loading logo: {e}")


def load_ratings():
    """Load ratings from JSON file, or return default ratings if file doesn't exist"""
    ratings_file = Path("ratings.json")
    if ratings_file.exists():
        with open(ratings_file, "r") as f:
            ratings_dict = json.load(f)
            # Convert the loaded dictionary back to TrueSkill ratings
            return {
                name: trueskill.Rating(mu=r["mu"], sigma=r["sigma"])
                for name, r in ratings_dict.items()
            }
    return {
        "Bav": env.Rating(),
        "Sam": env.Rating(),
        "Riz": env.Rating(),
        "Emily": env.Rating(),
    }


def load_history():
    """Load rating history from JSON file, or return empty history if file doesn't exist"""
    history_file = Path("ratings_history.json")
    if history_file.exists():
        with open(history_file, "r") as f:
            return json.load(f)
    return []


def save_ratings(ratings):
    """Save ratings to JSON file and update history"""
    # Save current ratings
    ratings_dict = {
        name: {"mu": float(r.mu), "sigma": float(r.sigma)}
        for name, r in ratings.items()
    }
    with open("ratings.json", "w") as f:
        json.dump(ratings_dict, f)

    # Update history
    history = load_history()
    timestamp = datetime.now().isoformat()
    history_entry = {"timestamp": timestamp, "ratings": ratings_dict}
    history.append(history_entry)

    # Save updated history
    with open("ratings_history.json", "w") as f:
        json.dump(history, f)


def get_ratings_df(ratings):
    """Convert ratings to a pandas DataFrame for display"""
    data = []
    for name, rating in ratings.items():
        data.append(
            {
                "Player": name,
                "Rating": round(rating.mu, 2),
                "Uncertainty": round(rating.sigma, 2),
            }
        )
    df = pd.DataFrame(data)
    return df.sort_values("Rating", ascending=False).reset_index(drop=True)


# Initialize session state
if "ratings" not in st.session_state:
    st.session_state.ratings = load_ratings()
if "history" not in st.session_state:
    st.session_state.history = load_history()

# Apply custom CSS to make the table larger
st.markdown(
    """
<style>
    .stDataFrame {
        font-size: 20px !important;
    }
    .stDataFrame td, .stDataFrame th {
        font-size: 22px !important;
        padding: 15px !important;
    }
    .stDataFrame th {
        background-color: #f0f2f6;
        font-weight: bold;
    }
</style>
""",
    unsafe_allow_html=True,
)

# App title with logo
col1, col2 = st.columns([1, 4])
with col1:
    if logo_loaded:
        st.image(uno_logo, width=100)
with col2:
    st.title("UNO Ranking")

# Create sidebar navigation
st.sidebar.title("Navigation")
page = st.sidebar.radio(
    "Go to", ["Rankings", "Rating History", "Add New Player", "Record Match Results"]
)

# Display current rankings (always visible)
if page == "Rankings":
    st.header("Current Rankings")
    rankings_df = get_ratings_df(st.session_state.ratings)

    # Display rankings as a list with metrics
    for i, row in rankings_df.iterrows():
        col1, col2, col3 = st.columns([1, 2, 2])

        with col1:
            st.markdown(f"### #{i+1}")

        with col2:
            st.markdown(f"### {row['Player']}")

        with col3:
            st.markdown(f"### Rating: {row['Rating']:.2f}")
            st.markdown(f"Uncertainty: ± {row['Uncertainty']:.2f}")

        st.divider()

# Display rating history
elif page == "Rating History":
    st.header("Rating History")

    if not st.session_state.history:
        st.info("No rating history available yet.")
    else:
        # Let user select a player to view history
        players = list(st.session_state.ratings.keys())
        selected_player = st.selectbox("Select Player", players)

        # Extract history data for the selected player
        history_data = []
        for entry in st.session_state.history:
            if selected_player in entry["ratings"]:
                history_data.append(
                    {
                        "Date": datetime.fromisoformat(entry["timestamp"]).strftime(
                            "%Y-%m-%d %H:%M"
                        ),
                        "Rating": round(entry["ratings"][selected_player]["mu"], 2),
                        "Uncertainty": round(
                            entry["ratings"][selected_player]["sigma"], 2
                        ),
                    }
                )

        if history_data:
            history_df = pd.DataFrame(history_data)

            # Plot rating over time
            st.subheader(f"{selected_player}'s Rating History")
            st.line_chart(history_df.set_index("Date")["Rating"])

            # Show history table
            st.subheader("Detailed History")
            st.dataframe(history_df, hide_index=True)
        else:
            st.info(f"No history available for {selected_player}.")

# Add new player section
elif page == "Add New Player":
    st.subheader("Add New Player")
    new_player = st.text_input("New Player Name")
    if st.button("Add Player"):
        if new_player and new_player not in st.session_state.ratings:
            st.session_state.ratings[new_player] = env.Rating()
            save_ratings(st.session_state.ratings)
            st.session_state.history = load_history()  # Reload history
            st.success(f"Added player: {new_player}")
            st.rerun()

# Record match results
elif page == "Record Match Results":
    st.subheader("Record Match Results")
    players = list(st.session_state.ratings.keys())
    num_players = st.number_input(
        "Number of players in match", min_value=2, max_value=len(players), value=2
    )

    match_players = []
    for i in range(num_players):
        player = st.selectbox(
            f"Player {i+1} (Position {i+1})", players, key=f"player_{i}"
        )
        match_players.append(player)

    if st.button("Record Match"):
        if len(match_players) == len(set(match_players)):  # Check for duplicates
            # Create teams and ratings lists
            teams = [[player] for player in match_players]
            team_ratings = [
                [st.session_state.ratings[player]] for player in match_players
            ]
            ranks = list(range(len(match_players)))

            # Update ratings
            updated_ratings = env.rate(team_ratings, ranks)

            # Update the ratings dictionary
            for i, player in enumerate(match_players):
                st.session_state.ratings[player] = updated_ratings[i][0]

            save_ratings(st.session_state.ratings)
            st.session_state.history = load_history()  # Reload history
            st.success("Match recorded successfully!")
            st.rerun()
        else:
            st.error("Each player can only appear once in a match!")
