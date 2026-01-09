# Contributing Guidelines

This document outlines the conventions and development processes we will follow.

## Issue Management

Use descriptive titles that clearly summarize the problem or feature request. 

If the issue relates to the test script, or changes in either the underlying CDL logic or device 
parameters needed to pass a test, use the tagging scheme described below. This will allow us to 
keep track of these changes to share with the broader G36 testing community.

### Issue Tagging
If an issue is related to one of the following areas and not necessarily our core code, start the issue title:

- `[Test Script]`: - an issue with the Test Script, including formatting, parsing, etc.
- `[CDL Logic]`:  - an issue involving the Modelica Buildings library implementation of G36 
- `[Device Model]` - an issue describing needed modification of the model being compiled into the device class (e.g., adjusting gains)


### Creating Issues
- Always create an issue before starting development work
- Provide clear descriptions with steps to reproduce (for bugs) or detailed requirements (for features)
- Include relevant context, screenshots, or code snippets when applicable
- Assign a person to resolve the issue if known
  - If working on the issue, be sure to assign yourself

## Development Process

### Process overview
1. **Create an Issue First**: All development work should be associated with an issue
2. **Create a Branch**: Follow branch naming convention (see below)
3. **Create Pull Request**: Clearly name and link to Issue
4. **Merge and Cleanup**: After PR is approved, merge into development branch, delete feature branch, link PR to Issue and vice versa.

### Branch Naming Convention
Use the following format for development branches:
```
issue<issue#>-<descriptor>
```

**Examples:**

- `issue42-fix-bug-description`
- `issue9-update-requirements`

### Pull Request Process
1. **Create Pull Request**: Submit a PR from your feature branch to the `develop` branch
2. **PR Naming**: Include the issue number in the PR title
   - Example: `Issue #42 - Update requirements.txt with simulation packages`
3. **PR Description**: 
   - Reference the issue being addressed (e.g., "Closes #42" or "Addresses #42")
     - If multiple issues are being addressed, link to each issue in the PR
   - Provide a clear description of changes made
   - Include any testing steps or considerations

### Code Review
- All PRs require review before merging

### Merging and Cleanup
1. **Close corresponding issue**: Close the corresponding issue with a comment linking to the merged PR
   - Example: "Resolved in PR #42" with a link to the PR
     - If a PR is resolving multiple issues, link the PR in each closed issues
2. **Delete Feature Branch**: Clean up by deleting the feature branch after successful merge
3. **Update Local Repository**: Pull latest changes to keep your local repo synchronized

## Code Style Guidelines

### General Style

- Follow PEP 8 style guide
- **Preferred linter format?**
  - Considering using a pre-commit formatter?!

### Docstring Format
We use **NumPy-style docstrings** for all functions, classes, and modules. This ensures consistent, readable documentation that integrates well with documentation generators.

#### Docstring Example
```python
def example_function(par1, par2=1):
    """
    Multi-line detailed description 
    or additional details as-needed.

    Parameters
    ----------
    par1: <str, float, int, bool, dict, list, pandas df, numpy array, etc.>
      Description of par1. If dict show format/fields. If list of what var type.
    par2: int, optional
      Description of par2.
      Default value is 1.

    Returns
    -------
    ret1: <str, float, int, bool, dict, list, pandas df, numpy array, etc.>
      Description of ret 1. If dict show format/fields. If list of what var type.
    ret2: <str, float, int, bool, dict, list, pandas df, numpy array, etc.>
      Description of ret 2. If dict show format/fields. If list of what var type.
    """
```


## Testing Guidelines
- Document guidelines for creating tests coming soon




