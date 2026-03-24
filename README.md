# ManBot

The Discord bot that acts as the official interface for ManGPT, developed by Team OpenDih.
ManBot is specifically trained on the anonymized chat messages from Manware Discord server.

<i>The bot is currently under development.</i>

## Contribution Guidelines

### Steps to install
1. Fork this repository.
2. Clone your forked repository to your local machine.
3. Run the requirements file: `pip install -r requirements.txt`
4. Create a new branch for your feature or bug fix.
5. Make your changes. Test it locally before creating a pull request.
6. Make a pull request to parent repository (OpenDih/ManBot)
7. Describe the changes made and why they're needed in the pull request description.
8. Wait for review from the Bot Lead.

### Reporting Issues
When reporting issues, please include:

- Detailed description of the problem
- Steps to reproduce
- Expected vs Actual behavior
- Environment details (Python version, etc.)

## Troubleshooting
### Bot won't start:

-Check if .env file exists and contains valid tokens
- Verify Discord token has proper permissions
- Ensure Python version is 3.8+

### Bot not responding:

- Check if bot has message permissions in the channel
- Verify the ManGPT API endpoint is accessible
- Check bot is mentioned or replied to correctly

### Connection issues:
- The bot includes automatic retry logic for connection problems
- Wait for exponential backoff to complete. It will attempt 5 times to reconnect.

## Support
For support and questions:

- Create an issue in the repository
- Contact the Bot Lead directly
- Check existing issues for similar problems

---

Developed by OpenDih.
