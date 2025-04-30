import streamlit as st
import trueskill
import json
from pathlib import Path
import pandas as pd
from PIL import Image
from datetime import datetime
import os
from github import Github

# Initialize TrueSkill environment
env = trueskill.TrueSkill(draw_probability=0.0)

# Load the UNO logo
try:
    uno_logo = Image.open("UNO_image.png")
    logo_loaded = True
except Exception as e:
    logo_loaded = False
    print(f"Error loading logo: {e}")


def setup_github_integration():
    """Setup GitHub integration using a personal access token"""
    # Get GitHub token from Streamlit secrets or environment variable
    github_token = (
        st.secrets["github"]["token"]
        if "github" in st.secrets
        else os.environ.get("GITHUB_TOKEN")
    )

    if not github_token:
        st.sidebar.warning(
            "GitHub token not found. Data changes will not be persisted between sessions."
        )
        return None

    try:
        # Initialize GitHub client
        g = Github(github_token)
        # Get the repository (format: "username/repo-name")
        repo_name = (
            st.secrets["github"]["repo"]
            if "github" in st.secrets
            else os.environ.get("GITHUB_REPO")
        )
        repo = g.get_repo(repo_name)
        return repo
    except Exception as e:
        st.sidebar.error(f"GitHub setup error: {e}")
        return None


# Initialize GitHub integration
github_repo = setup_github_integration()


def load_ratings():
    """Load ratings from GitHub or local JSON file"""
    if github_repo:
        try:
            contents = github_repo.get_contents("ratings.json")
            ratings_dict = json.loads(contents.decoded_content)
            # Convert the loaded dictionary back to TrueSkill ratings
            return {
                name: trueskill.Rating(mu=r["mu"], sigma=r["sigma"])
                for name, r in ratings_dict.items()
            }
        except Exception as e:
            st.sidebar.warning(f"Could not load ratings from GitHub: {e}")
            # Fall back to local file

    # Local file fallback
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
    """Load rating history from GitHub or local JSON file"""
    if github_repo:
        try:
            contents = github_repo.get_contents("ratings_history.json")
            return json.loads(contents.decoded_content)
        except Exception as e:
            st.sidebar.warning(f"Could not load history from GitHub: {e}")
            # Fall back to local file

    # Local file fallback
    history_file = Path("ratings_history.json")
    if history_file.exists():
        with open(history_file, "r") as f:
            return json.load(f)
    return []


def save_ratings(ratings):
    """Save ratings to GitHub and update history"""
    # Convert ratings to dictionary format
    ratings_dict = {
        name: {"mu": float(r.mu), "sigma": float(r.sigma)}
        for name, r in ratings.items()
    }

    # Save to GitHub if available
    if github_repo:
        try:
            # Save current ratings
            try:
                contents = github_repo.get_contents("ratings.json")
                github_repo.update_file(
                    contents.path,
                    "Update player ratings",
                    json.dumps(ratings_dict, indent=2),
                    contents.sha,
                )
            except:
                github_repo.create_file(
                    "ratings.json",
                    "Create player ratings file",
                    json.dumps(ratings_dict, indent=2),
                )

            # Update history
            timestamp = datetime.now().isoformat()
            history_entry = {"timestamp": timestamp, "ratings": ratings_dict}

            try:
                contents = github_repo.get_contents("ratings_history.json")
                history = json.loads(contents.decoded_content)
                history.append(history_entry)
                github_repo.update_file(
                    contents.path,
                    "Update ratings history",
                    json.dumps(history, indent=2),
                    contents.sha,
                )
            except:
                # Create new history file with first entry
                github_repo.create_file(
                    "ratings_history.json",
                    "Create ratings history file",
                    json.dumps([history_entry], indent=2),
                )

            return True
        except Exception as e:
            st.sidebar.error(f"Error saving to GitHub: {e}")
            # Fall back to local storage

    # Local file fallback
    with open("ratings.json", "w") as f:
        json.dump(ratings_dict, f)

    # Update local history
    history = load_history()
    timestamp = datetime.now().isoformat()
    history_entry = {"timestamp": timestamp, "ratings": ratings_dict}
    history.append(history_entry)

    # Save updated history locally
    with open("ratings_history.json", "w") as f:
        json.dump(history, f)

    return True


def get_ratings_df(ratings):
    """Convert ratings to a pandas DataFrame for display"""
    data = []
    for name, rating in ratings.items():
        conservative_rating = rating.mu - 3 * rating.sigma
        data.append(
            {
                "Player": name,
                "Rating": round(rating.mu, 2),
                "Uncertainty": round(rating.sigma, 2),
                "Conservative Rating": round(conservative_rating, 2),
            }
        )
    df = pd.DataFrame(data)
    return df.sort_values("Conservative Rating", ascending=False).reset_index(drop=True)


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

    # Initialize the show_raw_ratings state if it doesn't exist
    if "show_raw_ratings" not in st.session_state:
        st.session_state.show_raw_ratings = False

    # Toggle button for raw ratings
    if st.button(
        "Show Raw Ratings"
        if not st.session_state.show_raw_ratings
        else "Hide Raw Ratings"
    ):
        st.session_state.show_raw_ratings = not st.session_state.show_raw_ratings
        st.rerun()  # Force a rerun to update the UI immediately

    # Display rankings as a list with metrics
    for i, row in rankings_df.iterrows():
        col1, col2, col3 = st.columns([1, 2, 2])

        with col1:
            st.markdown(f"### #{i+1}")

        with col2:
            st.markdown(f"### {row['Player']}")

        with col3:
            if st.session_state.show_raw_ratings:
                st.markdown(
                    f"### Rating: {row['Rating']:.2f} ± {row['Uncertainty']:.2f}"
                )
            else:
                st.markdown(f"### Rating: {row['Conservative Rating']:.2f}")

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

# Add GitHub status indicator in sidebar
if github_repo:
    st.sidebar.success("GitHub integration active: Data will persist between sessions")
else:
    st.sidebar.warning("GitHub integration inactive: Data may be lost between sessions")
