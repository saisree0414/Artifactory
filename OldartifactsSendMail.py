pipeline {
    parameters {
        string(name: 'repository', description: 'Artifactory repository name')
        string(name: 'duration', description: 'Duration in ISO 8601 format, e.g., P6M')
        string(name: 'email', description: 'Email address to send the artifacts list')
    }

    agent any

    stages {
        stage('Fetch Artifacts') {
            steps {
                script {
                    def serverUrl = 'https://your-artifactory-instance'  // Replace with your Artifactory instance URL
                    def repoName = params.repository
                    def duration = params.duration
                    def email = params.email

                    def aqlQuery = """items.find(
                        {
                            "repo": "${repoName}",
                            "created": {"\$lt": "releaseArtifacts.find({\"repo\": \"${repoName}\", \"created\": {\"\$gt\": \"${duration}\"}}).max()"}
                        }
                    ).include("name", "repo", "path")"""

                    def artifacts = sh(script: "curl -u username:password -X POST -H 'Content-Type: text/plain' -d '${aqlQuery}' ${serverUrl}/artifactory/api/search/aql --insecure", returnStdout: true).trim()

                    if (artifacts) {
                        writeFile file: 'artifacts_list.txt', text: artifacts
                        echo 'Artifacts fetched successfully.'
                        emailext subject: 'Artifacts List - Older than 6 Months',
                                  body: 'Please find attached the list of artifacts older than 6 months.',
                                  to: email,
                                  attachmentsPattern: 'artifacts_list.txt'
                    } else {
                        error 'No artifacts found or failed to fetch artifacts from Artifactory.'
                    }
                }
            }
        }
    }
}
