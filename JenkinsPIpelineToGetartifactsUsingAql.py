pipeline {
    parameters {
        string(name: 'repository', description: 'Artifactory repository name')
        string(name: 'duration', description: 'Duration in ISO 8601 format, e.g., P6M')
    }

    agent any

    stages {
        stage('Fetch Artifacts') {
            steps {
                script {
                    def serverUrl = 'https://your-artifactory-instance'  // Replace with your Artifactory instance URL
                    def repoName = params.repository
                    def duration = params.duration

                    def aqlQuery = """items.find(
                        {
                            "repo": "${repoName}",
                            "created": {"\$lt": "releaseArtifacts.find({\"repo\": \"${repoName}\", \"created\": {\"\$gt\": \"${duration}\"}}).max()"}
                        }
                    ).include("name", "repo", "path")"""

                    def response = bat(script: "curl -u username:password -X POST -H 'Content-Type: text/plain' -d '${aqlQuery}' ${serverUrl}/artifactory/api/search/aql --insecure", returnStatus: true)

                    if (response == 0) {
                        echo 'Artifacts fetched successfully.'
                        // Process the retrieved artifacts as needed
                    } else {
                        error 'Failed to fetch artifacts from Artifactory.'
                    }
                }
            }
        }
    }
}
